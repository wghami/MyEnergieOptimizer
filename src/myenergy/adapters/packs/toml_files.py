"""Tariff packs as folders: ``pack.toml``, a ``rates/`` folder and an optional ``schedules.toml``.

``pack.toml`` describes the pack (ADR 0008)::

    [pack]
    name = "fr-household-vat-study"
    title = "French households, with VAT at 5.5 % on everything"
    extends = "fr-household"          # optional: inherit everything not redefined here
    max_kva = 36                      # optional
    tags = { country = "FR", purpose = "research" }

    [fields.status]                   # contract fields: allowed values, optional default
    values = ["consumer", "collective", "producer-injection"]
    default = "consumer"

    [network]                         # off-peak template on the contract's hours...
    seasons.high = { dates = "11-01..03-31", peak = "HPH", off_peak = "HCH" }
    seasons.low = { dates = "04-01..10-31", peak = "HPB", off_peak = "HCB" }
    # ...or year-round:  peak = "HP"  off_peak = "HC"
    # ...or fixed:       schedule = "<a schedule of schedules.toml>"

    [supply]                          # supply options, named by a field
    field = "supply_option"
    options.base = { single = "base" }
    options.hp-hc = { peak = "HP", off_peak = "HC" }

    [[checks]]                        # data, not code: errors or warnings
    level = "warning"
    message = "8 off-peak hours a day is the norm"
    when = { fta = ["CU4", "MU4"] }
    off_peak_hours = 8

A pack that ``extends`` another inherits it: tags and fields merge by name; ``max_kva``,
``network``, ``supply`` and ``checks`` are replaced when given (``checks = []`` drops them all);
a rate key or a schedule redefined here hides the inherited one.
"""

import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.rates.layered import LayeredRateSource
from myenergy.adapters.rates.toml_files import TomlRateSource
from myenergy.adapters.tariffs.schedules import load_schedules
from myenergy.domain.errors import ContractError, ScheduleError, UnknownPackError
from myenergy.domain.packs import (
    CheckLevel,
    ContractCheck,
    FieldSpec,
    OffPeakSeason,
    OffPeakTemplate,
    SupplyOption,
    TariffPack,
)
from myenergy.domain.schedules import Schedule, Season
from myenergy.ports.rates import RateSource

PACK_FILE = "pack.toml"
SCHEDULES_FILE = "schedules.toml"
RATES_FOLDER = "rates"
MAX_BYTES = 256 * 1024
"""A ``pack.toml`` or ``schedules.toml`` is small; larger ones are refused (SEC-1)."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _Header(_Strict):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    title: str = Field(min_length=1)
    extends: str | None = None
    max_kva: Decimal | int | None = None
    tags: dict[str, str] = Field(default_factory=dict[str, str])


class _Field(_Strict):
    values: list[str] = Field(min_length=1)
    default: str | None = None
    description: str = ""


class _Season(_Strict):
    dates: str
    peak: str
    off_peak: str


class _Network(_Strict):
    seasons: dict[str, _Season] | None = None
    peak: str | None = None
    off_peak: str | None = None
    schedule: str | None = None


class _Option(_Strict):
    single: str | None = None
    peak: str = "HP"
    off_peak: str = "HC"


class _Supply(_Strict):
    field: str
    options: dict[str, _Option] = Field(min_length=1)


class _Check(_Strict):
    message: str = Field(min_length=1)
    level: Literal["error", "warning"] = "error"
    when: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    require: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    off_peak_hours: float | int | None = None


class _PackFile(_Strict):
    pack: _Header
    fields: dict[str, _Field] = Field(default_factory=dict[str, _Field])
    network: _Network | None = None
    supply: _Supply | None = None
    checks: list[_Check] | None = None


@dataclass(frozen=True, slots=True)
class _Folder:
    path: Traversable
    parsed: _PackFile


def _read_text(path: Traversable, max_bytes: int) -> str:
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        msg = f"{path.name}: {len(raw)} bytes, more than the {max_bytes} allowed"
        raise DataFormatError(msg)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        msg = f"{path.name}: not UTF-8: {error}"
        raise DataFormatError(msg) from None


def _parse(folder: Traversable, max_bytes: int) -> _PackFile:
    where = f"{folder.name}/{PACK_FILE}"
    try:
        return _PackFile.model_validate(tomllib.loads(_read_text(folder / PACK_FILE, max_bytes)))
    except tomllib.TOMLDecodeError as error:
        msg = f"{where}: not valid TOML: {error}"
        raise DataFormatError(msg) from None
    except ValidationError as error:
        msg = f"{where}: {error}"
        raise DataFormatError(msg) from None


def _condition(raw: Mapping[str, list[str]]) -> tuple[tuple[str, frozenset[str]], ...]:
    return tuple((name, frozenset(values)) for name, values in sorted(raw.items()))


def _network(raw: _Network, schedules: Mapping[str, Schedule]) -> OffPeakTemplate | Schedule:
    if raw.schedule is not None:
        if raw.seasons is not None or raw.peak is not None or raw.off_peak is not None:
            msg = "network: give a schedule, or an off-peak template, not both"
            raise DataFormatError(msg)
        if raw.schedule not in schedules:
            msg = f"network: no schedule {raw.schedule!r} in {SCHEDULES_FILE}"
            raise DataFormatError(msg)
        return schedules[raw.schedule]
    if raw.seasons is not None:
        return OffPeakTemplate(
            tuple(
                OffPeakSeason(Season.parse(name, season.dates), season.peak, season.off_peak)
                for name, season in raw.seasons.items()
            )
        )
    return OffPeakTemplate((OffPeakSeason(None, raw.peak or "HP", raw.off_peak or "HC"),))


class TomlPackSource:
    """Every pack found in the given folders (each pack is a sub-folder with a ``pack.toml``)."""

    def __init__(self, roots: Iterable[Traversable], *, max_bytes: int = MAX_BYTES) -> None:
        """Find and read every pack; rates are read when first asked for.

        Raises:
            DataFormatError: a malformed pack, a name used twice, an unknown or circular
                ``extends``, or a pack that breaks a rule.
        """
        self._max_bytes = max_bytes
        self._folders: dict[str, _Folder] = {}
        for root in roots:
            for folder in sorted(root.iterdir(), key=lambda entry: entry.name):
                if not (folder.is_dir() and (folder / PACK_FILE).is_file()):
                    continue
                parsed = _parse(folder, max_bytes)
                name = parsed.pack.name
                if name in self._folders:
                    msg = f"two packs are called {name!r}: rename one, or make it extend the other"
                    raise DataFormatError(msg)
                self._folders[name] = _Folder(folder, parsed)
        self._schedules: dict[str, Mapping[str, Schedule]] = {}
        self._packs: dict[str, TariffPack] = {}
        self._rates: dict[str, RateSource] = {}
        self._own: dict[str, RateSource | None] = {}
        for name in self._folders:
            self._packs[name] = self._build(name, ())

    def _chain(self, name: str, seen: tuple[str, ...]) -> list[str]:
        """``name`` and its ancestors, ``name`` first."""
        if name in seen:
            msg = f"packs extend each other in a circle: {' -> '.join((*seen, name))}"
            raise DataFormatError(msg)
        if name not in self._folders:
            known = ", ".join(sorted(self._folders)) or "none"
            msg = f"{seen[-1]!r} extends {name!r}, which does not exist (packs: {known})"
            raise DataFormatError(msg)
        parent = self._folders[name].parsed.pack.extends
        return [name] if parent is None else [name, *self._chain(parent, (*seen, name))]

    def _own_schedules(self, name: str) -> Mapping[str, Schedule]:
        folder = self._folders[name].path
        path = folder / SCHEDULES_FILE
        if not path.is_file():
            return {}
        return load_schedules(
            _read_text(path, self._max_bytes), origin=f"{folder.name}/{SCHEDULES_FILE}"
        )

    def _build(self, name: str, seen: tuple[str, ...]) -> TariffPack:
        chain = self._chain(name, seen)
        merged: dict[str, Schedule] = {}
        for ancestor in reversed(chain):
            merged.update(self._own_schedules(ancestor))
        self._schedules[name] = merged
        files_ = [self._folders[ancestor].parsed for ancestor in reversed(chain)]
        try:
            return self._merge(files_, merged)
        except (ContractError, ScheduleError) as error:
            msg = f"{self._folders[name].path.name}/{PACK_FILE}: {error}"
            raise DataFormatError(msg) from None

    @staticmethod
    def _merge(chain: Sequence[_PackFile], schedules: Mapping[str, Schedule]) -> TariffPack:
        """The pack of ``chain[-1]``, on top of its ancestors ``chain[:-1]`` (oldest first)."""
        own = chain[-1].pack
        tags: dict[str, str] = {}
        fields: dict[str, FieldSpec] = {}
        max_kva: Decimal | None = None
        network: OffPeakTemplate | Schedule | None = None
        supply: _Supply | None = None
        checks: list[_Check] = []
        for parsed in chain:
            tags.update(parsed.pack.tags)
            for field_name, raw in parsed.fields.items():
                fields[field_name] = FieldSpec(
                    field_name, tuple(raw.values), raw.default, raw.description
                )
            if parsed.pack.max_kva is not None:
                max_kva = Decimal(parsed.pack.max_kva)
            if parsed.network is not None:
                network = _network(parsed.network, schedules)
            supply = parsed.supply or supply
            if parsed.checks is not None:
                checks = parsed.checks
        pack = TariffPack(
            name=own.name,
            title=own.title,
            tags=tuple(tags.items()),
            extends=own.extends,
            fields=tuple(fields.values()),
            max_kva=max_kva,
            checks=tuple(
                ContractCheck(
                    message=check.message,
                    level=CheckLevel(check.level),
                    when=_condition(check.when),
                    require=_condition(check.require),
                    off_peak_hours=None
                    if check.off_peak_hours is None
                    else float(check.off_peak_hours),
                )
                for check in checks
            ),
            supply_field=None if supply is None else supply.field,
            supply_options=()
            if supply is None
            else tuple(
                SupplyOption(option_name, option.single, option.peak, option.off_peak)
                for option_name, option in supply.options.items()
            ),
        )
        return pack if network is None else replace(pack, network=network)

    def catalog(self) -> Sequence[TariffPack]:
        """Every pack, sorted by name."""
        return [self._packs[name] for name in sorted(self._packs)]

    def pack(self, name: str) -> TariffPack:
        """The pack called ``name``.

        Raises:
            UnknownPackError: no such pack.
        """
        try:
            return self._packs[name]
        except KeyError:
            known = ", ".join(sorted(self._packs)) or "none"
            msg = f"no tariff pack {name!r} (packs: {known})"
            raise UnknownPackError(msg) from None

    def rates(self, name: str) -> RateSource:
        """The rates of pack ``name`` on top of those of the packs it extends.

        Raises:
            UnknownPackError: no such pack.
            DataFormatError: a malformed rate file.
        """
        self.pack(name)
        if name not in self._rates:
            chain = self._chain(name, ())
            layers = [layer for ancestor in chain if (layer := self._own_rates(ancestor))]
            self._rates[name] = LayeredRateSource(name, layers)
        return self._rates[name]

    def _own_rates(self, name: str) -> RateSource | None:
        """The rate files of pack ``name``'s own folder, read once and shared by its children."""
        if name not in self._own:
            folder = self._folders[name].path / RATES_FOLDER
            paths = (
                [path for path in folder.iterdir() if path.name.endswith(".toml")]
                if folder.is_dir()
                else []
            )
            self._own[name] = (
                TomlRateSource(paths, name=name, max_bytes=self._max_bytes * 4) if paths else None
            )
        return self._own[name]

    def schedules(self, name: str) -> Mapping[str, Schedule]:
        """The schedules pack ``name`` ships, inherited ones included.

        Raises:
            UnknownPackError: no such pack.
        """
        self.pack(name)
        return dict(self._schedules[name])


def builtin_packs() -> Traversable:
    """The folder of the packs shipped with the package."""
    return files("myenergy.adapters.packs") / "data"
