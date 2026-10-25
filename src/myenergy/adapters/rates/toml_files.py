"""Dated rates from TOML files, reviewed like code (ADR 0006).

A file declares the documents it cites under ``[sources.<id>]`` and its rates under ``[[rates]]``.
Each rate has a component, selectors, the unit **as published** (converted on load to a canonical
``RateUnit``) and versions. ``by`` names one more selector; a version's ``value`` is then a table
over it, for example the four time classes of one network option::

    [sources.cre-2025-78]
    title = "CRE deliberation n° 2025-78 of 2025-03-13: TURPE 7 HTA-BT from 2025-08-01"
    url = "https://www.cre.fr/..."

    [[rates]]
    component = "turpe.withdrawal.energy"
    selectors = { segment = "BT<=36kVA", fta = "CU4" }
    unit = "cEUR/kWh"
    by = "time_class"

    [[rates.versions]]
    from = 2025-08-01
    source = "cre-2025-78"
    status = "official"
    value = { HPH = 7.49, HCH = 3.97, HPB = 1.66, HCB = 1.16 }

Versions of one key may come from several files. A version without ``to`` lasts until the next
version of the same key starts, or stays open when it is the last. Anything malformed is a
``DataFormatError`` naming the file.
"""

import tomllib
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from importlib.resources.abc import Traversable
from itertools import pairwise
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from myenergy.adapters.errors import DataFormatError
from myenergy.domain.errors import RateError, UnknownRateError
from myenergy.domain.rates import RateHistory, RateKey, RateStatus, RateUnit, RateVersion

MAX_BYTES = 1024 * 1024
"""Rate files are small; larger inputs are refused (SEC-1)."""

PublishedUnit = Literal["EUR/year", "EUR/kVA/year", "EUR/kWh", "cEUR/kWh", "EUR/MWh", "%"]
UNITS: dict[str, tuple[RateUnit, Decimal]] = {
    "EUR/year": (RateUnit.EUR_PER_YEAR, Decimal(1)),
    "EUR/kVA/year": (RateUnit.EUR_PER_KVA_YEAR, Decimal(1)),
    "EUR/kWh": (RateUnit.EUR_PER_KWH, Decimal(1)),
    "cEUR/kWh": (RateUnit.EUR_PER_KWH, Decimal("0.01")),
    "EUR/MWh": (RateUnit.EUR_PER_KWH, Decimal("0.001")),
    "%": (RateUnit.FRACTION, Decimal("0.01")),
}
"""Published unit → canonical unit and the exact factor between them."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _Source(_Strict):
    title: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")


class _Version(_Strict):
    valid_from: date = Field(alias="from")
    valid_to: date | None = Field(default=None, alias="to")
    source: str
    status: RateStatus = Field(strict=False)
    value: Decimal | dict[str, Decimal]


class _Rate(_Strict):
    component: str = Field(min_length=1)
    selectors: dict[str, str] = Field(default_factory=dict[str, str])
    unit: PublishedUnit
    by: str | None = None
    versions: list[_Version] = Field(min_length=1)

    @model_validator(mode="after")
    def _values_match_by(self) -> Self:
        if self.by is not None and self.by in self.selectors:
            msg = f"'by' names {self.by!r}, which is already a selector"
            raise ValueError(msg)
        for version in self.versions:
            if (self.by is None) == isinstance(version.value, dict):
                msg = "a version's value is a table exactly when the rate has 'by'"
                raise ValueError(msg)
        return self


class _File(_Strict):
    sources: dict[str, _Source] = Field(default_factory=dict[str, _Source])
    rates: list[_Rate] = Field(min_length=1)


type _Pending = tuple[str, _Version, Decimal, RateUnit, str]
"""File name, raw version, value, unit, source text: a version before its end date is known."""


def _parse(name: str, text: str) -> _File:
    try:
        return _File.model_validate(tomllib.loads(text, parse_float=Decimal))
    except tomllib.TOMLDecodeError as error:
        msg = f"{name}: not valid TOML: {error}"
        raise DataFormatError(msg) from None
    except ValidationError as error:
        msg = f"{name}: {error}"
        raise DataFormatError(msg) from None


def _pairs(rate: _Rate, version: _Version) -> list[tuple[dict[str, str], Decimal]]:
    """Selectors and value of each key a version defines (one, or one per ``by`` value)."""
    if isinstance(version.value, dict):
        return [({**rate.selectors, str(rate.by): k}, v) for k, v in version.value.items()]
    return [(dict(rate.selectors), version.value)]


def _pending(name: str, parsed: _File) -> Iterable[tuple[RateKey, _Pending]]:
    for rate in parsed.rates:
        unit, factor = UNITS[rate.unit]
        for version in rate.versions:
            source = parsed.sources.get(version.source)
            if source is None:
                msg = f"{name}: {rate.component} cites an undeclared source {version.source!r}"
                raise DataFormatError(msg)
            cited = f"{source.title} <{source.url}>"
            for selectors, value in _pairs(rate, version):
                key = RateKey.of(rate.component, **selectors)
                yield key, (name, version, value * factor, unit, cited)


def _histories(pending: dict[RateKey, list[_Pending]]) -> dict[RateKey, RateHistory]:
    histories: dict[RateKey, RateHistory] = {}
    for key, items in pending.items():
        ordered = sorted(items, key=lambda item: item[1].valid_from)
        for before, after in pairwise(ordered):
            if before[1].valid_from == after[1].valid_from:
                msg = (
                    f"{key}: two versions start on {after[1].valid_from} ({before[0]}, {after[0]})"
                )
                raise DataFormatError(msg)
        starts: list[date | None] = [item[1].valid_from for item in ordered[1:]]
        starts.append(None)
        versions: list[RateVersion] = []
        for (name, raw, value, unit, cited), following in zip(ordered, starts, strict=True):
            try:
                versions.append(
                    RateVersion(
                        value=value,
                        unit=unit,
                        valid_from=raw.valid_from,
                        valid_to=raw.valid_to or following,
                        source=cited,
                        status=raw.status,
                    )
                )
            except RateError as error:
                msg = f"{name}: {key}: {error}"
                raise DataFormatError(msg) from None
        try:
            histories[key] = RateHistory(key, versions)
        except RateError as error:
            raise DataFormatError(str(error)) from None
    return histories


class TomlRateSource:
    """Rates read once from TOML files; the files together form one source."""

    def __init__(
        self,
        paths: Iterable[Traversable],
        *,
        name: str = "toml",
        max_bytes: int = MAX_BYTES,
    ) -> None:
        """Read and check every file in ``paths``.

        Raises:
            DataFormatError: a file is too large, malformed, or its versions overlap.
        """
        pending: dict[RateKey, list[_Pending]] = defaultdict(list)
        for path in sorted(paths, key=lambda path: path.name):
            raw = path.read_bytes()
            if len(raw) > max_bytes:
                msg = f"{path.name}: {len(raw)} bytes, more than the {max_bytes} allowed"
                raise DataFormatError(msg)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                msg = f"{path.name}: not UTF-8: {error}"
                raise DataFormatError(msg) from None
            for key, item in _pending(path.name, _parse(path.name, text)):
                pending[key].append(item)
        if not pending:
            msg = "no rate file given"
            raise DataFormatError(msg)
        self.name = name
        self._histories = _histories(pending)

    def catalog(self) -> Sequence[RateKey]:
        """Every key, sorted by component then selectors."""
        return sorted(self._histories, key=lambda key: (key.component, key.selectors))

    def history(self, key: RateKey) -> RateHistory:
        """Every version of ``key``.

        Raises:
            UnknownRateError: no file defines ``key``.
        """
        try:
            return self._histories[key]
        except KeyError:
            same = [str(known) for known in self._histories if known.component == key.component]
            hint = f"; known for {key.component}: {', '.join(same)}" if same else ""
            msg = f"no rate {key}{hint}"
            raise UnknownRateError(msg) from None
