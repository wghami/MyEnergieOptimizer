"""Dated rates: every regulated price is data with a validity period, a source and a status.

A ``RateKey`` names what is priced (a component and its selectors, such as the network option or
the time class); a ``RateHistory`` holds the successive ``RateVersion`` of one key. Values are
``Decimal`` in canonical units, so a rate reads exactly as published. Lookups are exact: a date
outside every version is an error, never the nearest value (SPEC decision 9, ADR 0006).
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise

from myenergy.domain.errors import CoverageError, RateError, UnverifiedRateError


class RateUnit(StrEnum):
    """Canonical units of rate values."""

    EUR_PER_YEAR = "EUR/year"
    EUR_PER_KVA_YEAR = "EUR/kVA/year"
    EUR_PER_KWH = "EUR/kWh"
    EUR_PER_MONTH = "EUR/month"
    EUR = "EUR"
    """A one-off amount."""
    FRACTION = "fraction"
    """A share of another amount: 0.2193 for 21.93 %."""


class RateStatus(StrEnum):
    """How far a value can be trusted."""

    OFFICIAL = "official"
    """Read in the regulator's, the operator's or the law's own publication."""
    TO_VERIFY = "to-verify"
    """From a secondary source or an agent; refused in bills unless explicitly allowed."""
    USER = "user"
    """Entered by the user (a supplier's prices from a bill or an offer); usable in bills."""


@dataclass(frozen=True, slots=True)
class RateKey:
    """What is priced: a component and the selectors that pick one value of it."""

    component: str
    selectors: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Keep selectors sorted, so equal keys compare and hash equal.

        Raises:
            RateError: the component is empty or a selector name repeats.
        """
        if not self.component:
            msg = "a rate key needs a component"
            raise RateError(msg)
        names = [name for name, _ in self.selectors]
        if len(set(names)) != len(names):
            msg = f"rate key {self.component!r} repeats a selector: {names}"
            raise RateError(msg)
        object.__setattr__(self, "selectors", tuple(sorted(self.selectors)))

    @classmethod
    def of(cls, component: str, **selectors: str) -> "RateKey":
        """``RateKey.of("turpe.withdrawal.power", segment="BT<=36kVA", fta="CU4")``."""
        return cls(component, tuple(selectors.items()))

    def __str__(self) -> str:
        """``component[name=value, ...]``."""
        inner = ", ".join(f"{name}={value}" for name, value in self.selectors)
        return f"{self.component}[{inner}]"


@dataclass(frozen=True, slots=True, kw_only=True)
class RateVersion:
    """One value of a rate over ``[valid_from, valid_to)``; ``valid_to=None`` means still valid."""

    value: Decimal
    unit: RateUnit
    valid_from: date
    valid_to: date | None
    source: str
    status: RateStatus

    def __post_init__(self) -> None:
        """Check the period and the provenance.

        Raises:
            RateError: an empty period, a non-finite value or no source.
        """
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            msg = f"empty validity period {self.valid_from} → {self.valid_to}"
            raise RateError(msg)
        if not self.value.is_finite():
            msg = f"rate value {self.value} is not finite"
            raise RateError(msg)
        if not self.source:
            msg = f"the rate valid from {self.valid_from} has no source"
            raise RateError(msg)

    def covers(self, day: date) -> bool:
        """Whether ``day`` lies in the validity period."""
        return self.valid_from <= day and (self.valid_to is None or day < self.valid_to)


class RateHistory:
    """The successive versions of one rate: one unit, no overlap; gaps are allowed."""

    def __init__(self, key: RateKey, versions: Iterable[RateVersion]) -> None:
        """Sort and check ``versions``.

        Raises:
            RateError: no version, mixed units, or two versions that overlap.
        """
        ordered = sorted(versions, key=lambda version: version.valid_from)
        if not ordered:
            msg = f"{key} has no version"
            raise RateError(msg)
        units = {version.unit for version in ordered}
        if len(units) > 1:
            msg = f"{key} mixes units: {sorted(units)}"
            raise RateError(msg)
        for before, after in pairwise(ordered):
            if before.valid_to is None or before.valid_to > after.valid_from:
                msg = f"{key}: the version from {before.valid_from} overlaps the next one"
                raise RateError(msg)
        self.key = key
        self.versions = tuple(ordered)

    @property
    def unit(self) -> RateUnit:
        """The unit of every version."""
        return self.versions[0].unit

    def __iter__(self) -> Iterator[RateVersion]:
        """The versions, oldest first."""
        return iter(self.versions)

    def between(
        self, start: date, end: date, *, allow_to_verify: bool = False
    ) -> tuple[RateVersion, ...]:
        """The versions that cover ``[start, end)`` without a gap, oldest first.

        Raises:
            CoverageError: a day of ``[start, end)`` that no version covers (the first one).
            UnverifiedRateError: a ``to-verify`` version in the period, unless allowed.
        """
        found: list[RateVersion] = []
        day = start
        while day < end:
            version = self.on(day, allow_to_verify=allow_to_verify)
            found.append(version)
            if version.valid_to is None:
                break
            day = version.valid_to
        return tuple(found)

    def on(self, day: date, *, allow_to_verify: bool = False) -> RateVersion:
        """The version valid on ``day``.

        Raises:
            CoverageError: no version covers ``day``.
            UnverifiedRateError: the version is ``to-verify`` and ``allow_to_verify`` is false.
        """
        for version in self.versions:
            if version.covers(day):
                if version.status is RateStatus.TO_VERIFY and not allow_to_verify:
                    msg = (
                        f"{self.key} on {day} is still to verify (source: {version.source}); "
                        "confirm it or allow unverified rates explicitly"
                    )
                    raise UnverifiedRateError(msg)
                return version
        periods = ", ".join(
            f"{version.valid_from} → {version.valid_to or 'open'}" for version in self.versions
        )
        msg = f"no version of {self.key} covers {day} (known: {periods})"
        raise CoverageError(msg)
