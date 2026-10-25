"""Resolve a price book against a contract and a bill period (ADR 0010).

Resolution decides which lines apply (``when``), finds each line's schedule periods and concrete
rate keys, checks that every rate covers the whole period with the right unit and status, orders
lines so that a percentage comes after what it is a percentage of, and reports **every** problem
at once. Amounts are computed from a resolved book (M2 task 5).
"""

import itertools
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from myenergy.domain.contract import Contract
from myenergy.domain.errors import (
    ContractError,
    CoverageError,
    PriceBookError,
    UnknownRateError,
    UnverifiedRateError,
)
from myenergy.domain.packs import TariffPack
from myenergy.domain.pricebooks import PERIOD, SUBSCRIBED_KVA, Inclusion, PriceBook, PriceLine
from myenergy.domain.rates import RateKey, RateVersion
from myenergy.domain.schedules import Schedule
from myenergy.ports.pricing import PriceBasis
from myenergy.ports.rates import RateSource


@dataclass(frozen=True, slots=True)
class ResolvedRate:
    """The rate of one combination of placeholder values (a period, a tier, ...)."""

    values: tuple[tuple[str, str], ...]
    """The expanded placeholders, e.g. ``(("period", "HPH"),)``; empty for a single rate."""
    key: RateKey
    versions: tuple[RateVersion, ...]
    """The versions covering the bill period, oldest first."""


@dataclass(frozen=True, slots=True)
class ResolvedLine:
    """A line ready to be computed."""

    line: PriceLine
    inclusion: Inclusion
    schedule: Schedule | None
    rates: tuple[ResolvedRate, ...]
    depends_on: tuple[str, ...]
    boundaries: tuple[date, ...]
    """Dates inside the bill period where one of the line's rates changes."""


@dataclass(frozen=True, slots=True)
class ResolvedBook:
    """Every applicable line of a book, resolved for one contract and period, in compute order."""

    book: PriceBook
    contract: Contract
    start: date
    end: date
    lines: tuple[ResolvedLine, ...]

    def line(self, name: str) -> ResolvedLine:
        """The resolved line called ``name``.

        Raises:
            PriceBookError: no such applicable line.
        """
        for resolved in self.lines:
            if resolved.line.name == name:
                return resolved
        raise PriceBookError([f"no applicable line {name!r}"])


@dataclass(frozen=True, slots=True, kw_only=True)
class PricingContext:
    """What a price book is resolved against: a contract under a pack, its rates, a period."""

    contract: Contract
    pack: TariffPack
    rates: RateSource
    start: date
    end: date
    """The bill period is ``[start, end)``, in local dates."""
    schedules: Mapping[str, Schedule] = field(default_factory=dict[str, Schedule])
    """Named schedules lines may use besides ``network`` and ``supply``."""
    allow_to_verify: bool = False


def _kva_text(contract: Contract) -> str:
    return format(contract.subscribed_kva.normalize(), "f")


class PriceBookResolver:
    """Resolves price books with the registered price bases."""

    def __init__(self, bases: Mapping[str, PriceBasis]) -> None:
        """Use these bases, by name."""
        self._bases = dict(bases)

    def _schedule(
        self,
        line: PriceLine,
        context: PricingContext,
        problems: list[str],
    ) -> Schedule | None:
        name = line.schedule
        if name is None:
            return None
        try:
            if name == "network":
                return context.pack.network_schedule(context.contract)
            if name == "supply":
                return context.pack.supply_schedule(context.contract)
        except ContractError as error:
            problems.append(f"line {line.name!r}: {error}")
            return None
        if name not in context.schedules:
            known = ", ".join(sorted(context.schedules)) or "none"
            problems.append(f"line {line.name!r}: no schedule {name!r} (network, supply, {known})")
            return None
        return context.schedules[name]

    def _rates(
        self,
        line: PriceLine,
        basis: PriceBasis,
        schedule: Schedule | None,
        context: PricingContext,
        problems: list[str],
    ) -> tuple[ResolvedRate, ...]:
        where = f"line {line.name!r}"
        if line.rate is None:
            if basis.units:
                problems.append(f"{where}: basis {basis.name!r} needs a rate")
            return ()
        expansions = dict(basis.expansions(line))
        if PERIOD in line.rate.placeholders:
            if schedule is None:
                problems.append(f"{where}: {{period}} needs a schedule")
                return ()
            expansions[PERIOD] = schedule.periods
        fixed = {**context.contract.selectors, SUBSCRIBED_KVA: _kva_text(context.contract)}
        names = sorted(expansions)
        found: list[ResolvedRate] = []
        for combination in itertools.product(*(expansions[n] for n in names)):
            values = tuple(zip(names, combination, strict=True))
            try:
                key = line.rate.key(fixed | dict(values))
                history = context.rates.history(key)
                versions = history.between(
                    context.start, context.end, allow_to_verify=context.allow_to_verify
                )
            except (PriceBookError, UnknownRateError, CoverageError, UnverifiedRateError) as error:
                problems.append(f"{where}: {error}")
                continue
            if history.unit not in basis.units:
                allowed = ", ".join(sorted(u.value for u in basis.units))
                problems.append(
                    f"{where}: {key} is in {history.unit.value}; {basis.name} takes {allowed}"
                )
                continue
            found.append(ResolvedRate(values=values, key=key, versions=versions))
        return tuple(found)

    def resolve(self, book: PriceBook, context: PricingContext) -> ResolvedBook:
        """The applicable lines of ``book`` for the context's contract and period, in order.

        Raises:
            PriceBookError: every problem found: an unknown basis or schedule, bad parameters, a
                missing flow, a rate that is missing, of the wrong unit, not covering the period
                or still to verify, an unknown or circular line reference, an empty period.
        """
        start, end = context.start, context.end
        problems = [] if start < end else [f"the bill period {start} -> {end} is empty"]
        applicable = PriceBook(
            name=book.name,
            lines=tuple(line for line in book.lines if line.applies_to(context.contract)),
            inclusion=book.inclusion,
            settings=book.settings,
        )
        resolved: dict[str, ResolvedLine] = {}
        for line in applicable.lines:
            basis = self._bases.get(line.basis)
            if basis is None:
                known = ", ".join(sorted(self._bases)) or "none"
                problems.append(
                    f"line {line.name!r}: no price basis {line.basis!r} (bases: {known})"
                )
                continue
            problems.extend(basis.problems(line))
            if basis.needs_flow != (line.flow is not None):
                needed = "needs a" if basis.needs_flow else "takes no"
                problems.append(f"line {line.name!r}: basis {basis.name!r} {needed} flow")
            schedule = self._schedule(line, context, problems)
            line_rates = self._rates(line, basis, schedule, context, problems)
            boundaries = sorted(
                {v.valid_from for r in line_rates for v in r.versions if start < v.valid_from < end}
            )
            resolved[line.name] = ResolvedLine(
                line=line,
                inclusion=applicable.inclusion_of(line),
                schedule=schedule,
                rates=line_rates,
                depends_on=basis.depends_on(line, applicable),
                boundaries=tuple(boundaries),
            )
        ordered = _ordered(resolved, problems)
        if problems:
            raise PriceBookError(problems)
        return ResolvedBook(
            book=applicable, contract=context.contract, start=start, end=end, lines=ordered
        )


def _ordered(resolved: Mapping[str, ResolvedLine], problems: list[str]) -> tuple[ResolvedLine, ...]:
    """Lines after those they depend on; unknown references and cycles become problems."""
    for name, line in resolved.items():
        unknown = [d for d in line.depends_on if d not in resolved]
        if unknown:
            problems.append(f"line {name!r} refers to lines that do not apply or exist: {unknown}")
    ordered: list[ResolvedLine] = []
    placed: set[str] = set()
    remaining = dict(resolved)
    while remaining:
        ready = [
            n for n, line in remaining.items() if set(line.depends_on) & set(resolved) <= placed
        ]
        if not ready:
            problems.append(f"lines refer to each other in a circle: {sorted(remaining)}")
            break
        for name in ready:
            ordered.append(remaining.pop(name))
            placed.add(name)
    return tuple(ordered)
