"""Tariff packs: user-definable rules that give contract fields their meaning.

A pack says which **fields** a contract has and which values they may take, the subscribed-power
limit, **checks** (errors or warnings, written as data), how a contract's off-peak hours become
its **network schedule**, and which **supply options** exist. Its rates live beside it (see
``myenergy.ports.packs``). Packs are data: the built-in French household pack is one of them, and
users write their own, from scratch or by extending another, for another country, a research
scenario or a tax study. Free **tags** (``country``, ``sector``, ``purpose``, …) describe a pack.
"""

import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import StrEnum

from myenergy.domain.contract import Contract
from myenergy.domain.errors import ContractError, TariffWarning
from myenergy.domain.schedules import NO_WINDOWS, PeriodRule, Schedule, Season, TimeWindows


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """A contract field: its allowed values and its default (``None``: the field is required)."""

    name: str
    values: tuple[str, ...]
    default: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        """Check the spec.

        Raises:
            ContractError: no name, no values, or a default outside the values.
        """
        if not self.name or not self.values:
            msg = f"field {self.name!r} needs a name and at least one value"
            raise ContractError(msg)
        if self.default is not None and self.default not in self.values:
            msg = f"field {self.name!r}: default {self.default!r} is not one of {list(self.values)}"
            raise ContractError(msg)


class CheckLevel(StrEnum):
    """What a failed check does."""

    ERROR = "error"
    """The contract is refused."""
    WARNING = "warning"
    """A ``TariffWarning``; the contract is priced as given."""


type Condition = tuple[tuple[str, frozenset[str]], ...]
"""Fields and the values each may take: ``(("fta", {"CU4", "MU4"}),)``."""


def _matches(condition: Condition, fields: Mapping[str, str]) -> bool:
    return all(fields.get(name) in values for name, values in condition)


@dataclass(frozen=True, slots=True)
class ContractCheck:
    """When the contract matches ``when``, it must match ``require`` and have ``off_peak_hours``."""

    message: str
    level: CheckLevel = CheckLevel.ERROR
    when: Condition = ()
    require: Condition = ()
    off_peak_hours: float | None = None
    """Hours of off-peak a day, in every season of the network schedule."""

    def failures(self, contract: Contract, seasons: tuple[str | None, ...]) -> list[str]:
        """Why ``contract`` fails this check (empty when it passes)."""
        fields = contract.selectors
        if not _matches(self.when, fields):
            return []
        found: list[str] = []
        if not _matches(self.require, fields):
            found.append(self.message)
        if self.off_peak_hours is not None:
            for season in seasons:
                hours = contract.off_peak_for(season)
                if hours.hours != self.off_peak_hours:
                    where = f" in season {season}" if season else ""
                    found.append(
                        f"{self.message} (off-peak hours{where}: {hours}, {hours.hours:g} h)"
                    )
        return found


@dataclass(frozen=True, slots=True)
class OffPeakSeason:
    """A season of an off-peak template and the names of its peak and off-peak periods."""

    season: Season | None
    """``None``: the whole year."""
    peak: str
    off_peak: str


@dataclass(frozen=True, slots=True)
class OffPeakTemplate:
    """Builds a schedule from a contract's off-peak hours: peak and off-peak, per season."""

    seasons: tuple[OffPeakSeason, ...]

    def __post_init__(self) -> None:
        """Check the seasons.

        Raises:
            ContractError: not exactly one year-round entry nor only dated seasons.
            ScheduleError: dated seasons that do not cover each date of the year once.
        """
        dated = tuple(entry.season for entry in self.seasons if entry.season is not None)
        valid = len(dated) == len(self.seasons) if dated else len(self.seasons) == 1
        if not valid:
            msg = "an off-peak template has one year-round entry, or seasons covering the year"
            raise ContractError(msg)
        if dated:
            Schedule(name="off-peak template", default="peak", seasons=dated)

    @property
    def season_names(self) -> tuple[str | None, ...]:
        """The seasons' names (``None`` for a year-round template)."""
        return tuple(None if e.season is None else e.season.name for e in self.seasons)

    def renamed(self, peak: str, off_peak: str) -> "OffPeakTemplate":
        """The same seasons with other period names (one pair for every season)."""
        return OffPeakTemplate(tuple(OffPeakSeason(e.season, peak, off_peak) for e in self.seasons))

    def build(self, name: str, contract: Contract) -> Schedule:
        """The schedule of ``contract``'s off-peak hours."""
        rules: list[PeriodRule] = []
        seasons: list[Season] = []
        for entry in self.seasons:
            if entry.season is None:
                rules.append(PeriodRule(entry.off_peak, contract.off_peak_for(None)))
                return Schedule(name=name, rules=tuple(rules), default=entry.peak)
            season = entry.season
            seasons.append(Season(season.name, season.first, season.last, default=entry.peak))
            only = frozenset({season.name})
            rules.append(
                PeriodRule(entry.off_peak, contract.off_peak_for(season.name), seasons=only)
            )
        return Schedule(name=name, rules=tuple(rules), seasons=tuple(seasons))


YEAR_ROUND = OffPeakTemplate((OffPeakSeason(None, "HP", "HC"),))
"""Peak and off-peak all year, on the contract's off-peak hours."""


@dataclass(frozen=True, slots=True)
class SupplyOption:
    """A supply option: one period all the time, or peak/off-peak on the contract's hours."""

    name: str
    single: str | None = None
    """The one period of a single-price option."""
    peak: str = "HP"
    off_peak: str = "HC"


@dataclass(frozen=True, slots=True, kw_only=True)
class TariffPack:
    """The rules of one tariff framework. Rates are provided alongside, by a ``PackSource``."""

    name: str
    title: str
    tags: tuple[tuple[str, str], ...] = ()
    """Free tags, e.g. ``(("country", "FR"), ("sector", "household"))``."""
    extends: str | None = None
    fields: tuple[FieldSpec, ...] = ()
    max_kva: Decimal | None = None
    checks: tuple[ContractCheck, ...] = ()
    network: OffPeakTemplate | Schedule = YEAR_ROUND
    """How the network schedule is built: a template on the contract's hours, or a fixed one."""
    supply_field: str | None = None
    """The field that names the supply option."""
    supply_options: tuple[SupplyOption, ...] = ()
    sharing_step: timedelta | None = None
    """The step at which shared energy is allocated, if the pack says (e.g. 30 minutes)."""

    def __post_init__(self) -> None:
        """Check the pack's own consistency.

        Raises:
            ContractError: no name, repeated fields, or a supply field that is not declared.
        """
        if not self.name:
            msg = "a tariff pack needs a name"
            raise ContractError(msg)
        names = [spec.name for spec in self.fields]
        if len(set(names)) != len(names):
            msg = f"pack {self.name!r} repeats a field: {names}"
            raise ContractError(msg)
        options = {option.name for option in self.supply_options}
        if self.supply_field is not None:
            spec = next((s for s in self.fields if s.name == self.supply_field), None)
            if spec is None or set(spec.values) != options:
                msg = (
                    f"pack {self.name!r}: supply field {self.supply_field!r} must be a field whose "
                    f"values are the supply options {sorted(options)}"
                )
                raise ContractError(msg)
        object.__setattr__(self, "tags", tuple(sorted(self.tags)))

    def tag(self, key: str) -> str | None:
        """The value of tag ``key``, if any."""
        return dict(self.tags).get(key)

    def _seasons(self) -> tuple[str | None, ...]:
        if isinstance(self.network, OffPeakTemplate):
            return self.network.season_names
        return (None,)

    def _fields(self, given: Mapping[str, str]) -> dict[str, str]:
        specs = {spec.name: spec for spec in self.fields}
        unknown = sorted(set(given) - set(specs))
        if unknown:
            msg = f"pack {self.name!r} has no field {unknown} (fields: {', '.join(specs)})"
            raise ContractError(msg)
        found: dict[str, str] = {}
        for spec in self.fields:
            value = given.get(spec.name, spec.default)
            if value is None:
                msg = f"pack {self.name!r}: field {spec.name!r} is required ({list(spec.values)})"
                raise ContractError(msg)
            if value not in spec.values:
                msg = (
                    f"pack {self.name!r}: {spec.name} = {value!r} is not one of {list(spec.values)}"
                )
                raise ContractError(msg)
            found[spec.name] = value
        return found

    def _apply_checks(self, contract: Contract) -> None:
        if self.max_kva is not None and contract.subscribed_kva > self.max_kva:
            msg = (
                f"pack {self.name!r} allows up to {self.max_kva} kVA, got {contract.subscribed_kva}"
            )
            raise ContractError(msg)
        for check in self.checks:
            for failure in check.failures(contract, self._seasons()):
                message = f"pack {self.name!r}: {failure}"
                if check.level is CheckLevel.ERROR:
                    raise ContractError(message)
                warnings.warn(message, TariffWarning, stacklevel=3)

    def contract(
        self,
        *,
        subscribed_kva: Decimal | int | str,
        fields: Mapping[str, str] | None = None,
        off_peak: TimeWindows = NO_WINDOWS,
        seasonal_off_peak: Mapping[str, TimeWindows] | None = None,
        network: Schedule | None = None,
        supply: Schedule | None = None,
    ) -> Contract:
        """A contract under this pack, with defaults filled in and every check applied.

        Raises:
            ContractError: an unknown or missing field, a value not allowed, a power above the
                limit, an unknown season, or a failed check of level ``error``.

        Warns:
            TariffWarning: a failed check of level ``warning``.
        """
        seasonal = dict(seasonal_off_peak or {})
        unknown_seasons = sorted(set(seasonal) - {s for s in self._seasons() if s})
        if unknown_seasons:
            msg = f"pack {self.name!r} has no season {unknown_seasons}"
            raise ContractError(msg)
        contract = Contract(
            pack=self.name,
            subscribed_kva=Decimal(subscribed_kva),
            fields=tuple(self._fields(fields or {}).items()),
            off_peak=off_peak,
            seasonal_off_peak=tuple(seasonal.items()),
            network=network,
            supply=supply,
        )
        self._apply_checks(contract)
        return contract

    def network_schedule(self, contract: Contract) -> Schedule:
        """The contract's own network schedule, or the pack's, built from its off-peak hours."""
        if contract.network is not None:
            return contract.network
        if isinstance(self.network, Schedule):
            return self.network
        return self.network.build(f"{self.name}/network", contract)

    def supply_schedule(self, contract: Contract) -> Schedule:
        """The contract's own supply schedule, or the one of its supply option.

        Raises:
            ContractError: neither is available.
        """
        if contract.supply is not None:
            return contract.supply
        if self.supply_field is None:
            msg = f"pack {self.name!r} has no supply options; give the contract a supply schedule"
            raise ContractError(msg)
        chosen = contract.field(self.supply_field)
        option = next(option for option in self.supply_options if option.name == chosen)
        name = f"{self.name}/{option.name}"
        if option.single is not None:
            return Schedule(name=name, default=option.single)
        template = self.network if isinstance(self.network, OffPeakTemplate) else YEAR_ROUND
        return template.renamed(option.peak, option.off_peak).build(name, contract)


def tagged(packs: Iterable[TariffPack], **tags: str) -> list[TariffPack]:
    """The packs having every tag given, e.g. ``tagged(packs, country="FR")``."""
    return [pack for pack in packs if all(pack.tag(key) == value for key, value in tags.items())]
