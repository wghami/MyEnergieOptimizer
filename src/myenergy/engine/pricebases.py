"""Built-in price bases, registered as entry points like any third party's (ADR 0010)."""

from collections.abc import Mapping
from decimal import Decimal
from typing import cast

from myenergy.domain.pricebooks import Inclusion, PriceBook, PriceLine
from myenergy.domain.rates import RateUnit

RESETS = frozenset({"month", "year", "bill"})


def _list(value: object) -> list[object] | None:
    """``value`` as a list of untyped items, if it is a list (TOML parameters are untyped)."""
    return list(cast("list[object]", value)) if isinstance(value, list) else None


def _table(value: object) -> Mapping[str, object] | None:
    """``value`` as a table, if it is one."""
    return cast("Mapping[str, object]", value) if isinstance(value, Mapping) else None


class _Simple:
    """A basis with no parameters of its own."""

    def __init__(self, name: str, units: frozenset[RateUnit], *, needs_flow: bool) -> None:
        self.name = name
        self.units = units
        self.needs_flow = needs_flow

    def problems(self, line: PriceLine) -> list[str]:
        """Parameters this basis does not take."""
        if line.params:
            return [f"line {line.name!r}: basis {self.name!r} takes no {sorted(line.params)}"]
        return []

    def expansions(self, line: PriceLine) -> Mapping[str, tuple[str, ...]]:
        """None."""
        del line  # no placeholder of its own
        return {}

    def depends_on(self, line: PriceLine, book: PriceBook) -> tuple[str, ...]:
        """None: the amount comes from the line's own flow or rate."""
        del line, book  # independent of other lines
        return ()


FIXED = _Simple(
    "fixed",
    frozenset({RateUnit.EUR_PER_YEAR, RateUnit.EUR_PER_KVA_YEAR, RateUnit.EUR_PER_MONTH}),
    needs_flow=False,
)
"""A yearly or monthly charge (per kVA if the rate is per kVA), prorated over the bill period."""
PER_KWH = _Simple("per_kwh", frozenset({RateUnit.EUR_PER_KWH}), needs_flow=True)
"""The line's flow in each period, times that period's rate."""
ONCE = _Simple("once", frozenset({RateUnit.EUR}), needs_flow=False)
"""A one-off amount, charged once per bill."""


class TieredBasis:
    """Price per kWh by tranche of energy accumulated over a reset period (``{tier}``)."""

    name = "tiered_per_kwh"
    units = frozenset({RateUnit.EUR_PER_KWH})
    needs_flow = True

    @staticmethod
    def _tiers(line: PriceLine) -> list[Mapping[str, object]] | None:
        items = _list(line.params.get("tiers"))
        tables = [_table(item) for item in items or []]
        if not tables or any(table is None for table in tables):
            return None
        return [table for table in tables if table is not None]

    def problems(self, line: PriceLine) -> list[str]:
        """``reset`` and ascending ``tiers`` (each named; all but the last with ``up_to_kwh``)."""
        where = f"line {line.name!r}"
        found: list[str] = []
        if line.params.get("reset") not in RESETS:
            found.append(f"{where}: reset must be one of {sorted(RESETS)}")
        unknown = sorted(set(line.params) - {"reset", "tiers"})
        if unknown:
            found.append(f"{where}: unknown parameters {unknown}")
        if line.rate is None or "tier" not in line.rate.placeholders:
            found.append(f"{where}: the rate selectors must use {{tier}}")
        tiers = self._tiers(line)
        if tiers is None:
            return [*found, f"{where}: tiers must be a non-empty list of tables"]
        names = [tier.get("name") for tier in tiers]
        if not all(isinstance(n, str) and n for n in names) or len(set(names)) != len(names):
            found.append(f"{where}: every tier needs a distinct name")
        bounds = [tier.get("up_to_kwh") for tier in tiers]
        upper = [float(b) for b in bounds[:-1] if isinstance(b, int | float | Decimal) and b > 0]
        if len(upper) != len(bounds) - 1 or upper != sorted(set(upper)) or bounds[-1] is not None:
            found.append(f"{where}: up_to_kwh must rise, and the last tier has none")
        return found

    def expansions(self, line: PriceLine) -> Mapping[str, tuple[str, ...]]:
        """``{tier}``: the tier names."""
        return {"tier": tuple(str(tier.get("name")) for tier in self._tiers(line) or [])}

    def depends_on(self, line: PriceLine, book: PriceBook) -> tuple[str, ...]:
        """None."""
        del line, book  # independent of other lines
        return ()


class PercentOfBasis:
    """A share of other lines.

    ``of`` names lines (itemised or included); ``of_vat`` takes every itemised line of a VAT
    category.
    """

    name = "percent_of"
    units = frozenset({RateUnit.FRACTION})
    needs_flow = False

    def problems(self, line: PriceLine) -> list[str]:
        """Exactly one of ``of`` (a list of line names) or ``of_vat`` (a category)."""
        where = f"line {line.name!r}"
        of = _list(line.params.get("of"))
        of_vat = line.params.get("of_vat")
        named = bool(of) and all(isinstance(name, str) for name in of or [])
        category = isinstance(of_vat, str) and bool(of_vat)
        found = [] if named != category else [f"{where}: give either of (line names) or of_vat"]
        unknown = sorted(set(line.params) - {"of", "of_vat"})
        if unknown:
            found.append(f"{where}: unknown parameters {unknown}")
        if line.flow is not None:
            found.append(f"{where}: a percentage of other lines has no flow")
        return found

    def expansions(self, line: PriceLine) -> Mapping[str, tuple[str, ...]]:
        """None."""
        del line  # no placeholder of its own
        return {}

    def depends_on(self, line: PriceLine, book: PriceBook) -> tuple[str, ...]:
        """The named lines, or every itemised line of the VAT category."""
        of = _list(line.params.get("of"))
        if of is not None:
            return tuple(str(name) for name in of)
        category = line.params.get("of_vat")
        return tuple(
            other.name
            for other in book.lines
            if other.vat == category and book.inclusion_of(other) is Inclusion.ITEMISED
        )


TIERED = TieredBasis()
PERCENT_OF = PercentOfBasis()
