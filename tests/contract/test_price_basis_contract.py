"""Every ``PriceBasis`` honours the same contract (PRT-1), including test-only ones (PRT-2)."""

from collections.abc import Mapping

import pytest

from myenergy.domain.flows import FlowKind
from myenergy.domain.pricebooks import PriceBook, PriceLine
from myenergy.domain.rates import RateUnit
from myenergy.engine.pricebases import FIXED, ONCE, PER_KWH, PERCENT_OF, TIERED
from myenergy.ports.pricing import PriceBasis


class PowerOverrun:
    """A test-only basis, written against the port only: a charge per kVA above subscription."""

    name = "power_overrun"
    units = frozenset({RateUnit.EUR_PER_KVA_YEAR})
    needs_flow = False

    def problems(self, line: PriceLine) -> list[str]:
        return (
            [] if set(line.params) <= {"threshold_kva"} else [f"line {line.name!r}: bad parameters"]
        )

    def expansions(self, line: PriceLine) -> Mapping[str, tuple[str, ...]]:
        del line  # no placeholder of its own
        return {}

    def depends_on(self, line: PriceLine, book: PriceBook) -> tuple[str, ...]:
        del line, book  # independent of other lines
        return ()


BASES: dict[str, PriceBasis] = {
    b.name: b for b in (FIXED, PER_KWH, TIERED, PERCENT_OF, ONCE, PowerOverrun())
}


@pytest.fixture(params=sorted(BASES))
def basis(request: pytest.FixtureRequest) -> PriceBasis:
    return BASES[request.param]


def test_bases_satisfy_the_port(basis: PriceBasis) -> None:
    assert isinstance(basis, PriceBasis)
    assert basis.name
    assert all(isinstance(unit, RateUnit) for unit in basis.units)


def test_unknown_parameters_are_reported(basis: PriceBasis) -> None:
    flow = FlowKind.IMPORT if basis.needs_flow else None
    line = PriceLine(name="x", basis=basis.name, flow=flow, params={"no_such_parameter": 1})
    assert basis.problems(line)
    assert isinstance(basis.depends_on(line, PriceBook(name="b")), tuple)
