"""Site flows: metered, self-consumed and shared energy, with every invariant checked."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from myenergy.domain.errors import FlowError
from myenergy.domain.flows import FlowKind, SharedFlow, SiteFlows
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.sites import ShareDirection
from myenergy.domain.time import TimeGrid

START = datetime(2026, 6, 1, 12, tzinfo=UTC)
GRID = TimeGrid(start=START, end=START + timedelta(hours=1), step=timedelta(minutes=15))


def kw(*values: float) -> TimeSeries:
    return TimeSeries(
        grid=GRID, values=np.array(values, dtype=np.float64), quantity=Quantity.POWER_KW
    )


def kwh(*values: float) -> TimeSeries:
    return TimeSeries(
        grid=GRID, values=np.array(values, dtype=np.float64), quantity=Quantity.ENERGY_KWH
    )


def test_flows_from_signed_powers() -> None:
    pv = kw(4, 4, 0, 0)
    house = kw(-2, -2, -2, -2)
    car = kw(0, -4, 0, 0)
    flows = SiteFlows.from_powers("home", [pv, house, car])
    assert flows.imported.values.tolist() == [0, 0.5, 0.5, 0.5]
    assert flows.exported.values.tolist() == [0.5, 0, 0, 0]
    assert flows.self_consumed.values.tolist() == [0.5, 1.0, 0, 0]
    assert flows.totals()[FlowKind.SUPPLIED] == 1.5
    assert flows.totals()[FlowKind.SOLD] == 0.5


def test_shared_energy_splits_import_and_export() -> None:
    flows = SiteFlows.measured(
        "home",
        imported=kwh(1, 1, 0, 0),
        exported=kw(0, 0, 4, 4),
        shared=[
            SharedFlow(ShareDirection.IN, "op", kwh(0.25, 0.5, 0, 0)),
            SharedFlow(ShareDirection.IN, "neighbour", kwh(0.25, 0, 0, 0)),
            SharedFlow(ShareDirection.OUT, "op", kwh(0, 0, 0.5, 0)),
        ],
    )
    assert flows.flow(FlowKind.SHARED_IN).values.tolist() == [0.5, 0.5, 0, 0]
    assert flows.flow(FlowKind.SUPPLIED).values.tolist() == [0.5, 0.5, 0, 0]
    assert flows.flow(FlowKind.SOLD).values.tolist() == [0, 0, 0.5, 1.0]
    assert flows.flow(FlowKind.SHARED_IN, "neighbour").values.tolist() == [0.25, 0, 0, 0]
    assert flows.flow(FlowKind.SHARED_OUT, "op").total() == 0.5
    assert flows.self_consumed.total() == 0
    assert flows.counterparties == {
        ShareDirection.IN: ("op", "neighbour"),
        ShareDirection.OUT: ("op",),
    }


def test_a_measured_step_may_hold_import_and_export() -> None:
    flows = SiteFlows.measured(
        "home",
        imported=kwh(0.5, 0, 0, 0),
        exported=kwh(0.5, 0, 0, 0),
        self_consumed=kwh(0, 1, 0, 0),
    )
    assert flows.totals()[FlowKind.IMPORT] == flows.totals()[FlowKind.EXPORT] == 0.5
    assert flows.totals()[FlowKind.SELF_CONSUMPTION] == 1


@pytest.mark.parametrize(
    ("kind", "counterparty", "message"),
    [
        (FlowKind.IMPORT, "op", "import has no counterparty"),
        (FlowKind.SHARED_IN, "nobody", "shares nothing in with 'nobody'"),
    ],
)
def test_counterparty_lookups(kind: FlowKind, counterparty: str, message: str) -> None:
    flows = SiteFlows.measured(
        "home",
        imported=kwh(1, 1, 1, 1),
        exported=kwh(0, 0, 0, 0),
        shared=[SharedFlow(ShareDirection.IN, "op", kwh(1, 0, 0, 0))],
    )
    with pytest.raises(FlowError, match=message):
        flows.flow(kind, counterparty)


OTHER = TimeGrid(start=START, end=START + timedelta(hours=1), step=timedelta(minutes=30))


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"imported": kwh(-1, 0, 0, 0)}, "import is negative at step 0"),
        ({"exported": kw(0, 0, 0, 0)}, "export must be kWh"),
        (
            {"self_consumed": TimeSeries.constant(OTHER, 0, Quantity.ENERGY_KWH)},
            "self_consumption must be kWh",
        ),
        (
            {"shared": (SharedFlow(ShareDirection.IN, "op", kwh(0, 2, 0, 0)),)},
            r"shared in exceeds import at 2026-06-01 14:15 CEST by 1 kWh",
        ),
        (
            {"shared": (SharedFlow(ShareDirection.OUT, "op", kwh(0, 0, 0, 0.5)),)},
            "shared out exceeds export",
        ),
        (
            {"shared": (SharedFlow(ShareDirection.IN, "op", kwh(0, 0, 0, 0)),) * 2},
            "shares twice",
        ),
        (
            {"shared": (SharedFlow(ShareDirection.IN, "op", kwh(-1, 0, 0, 0)),)},
            "shared in op is negative",
        ),
    ],
)
def test_invariants(arguments: dict[str, object], message: str) -> None:
    fields: dict[str, object] = {
        "site": "home",
        "grid": GRID,
        "imported": kwh(1, 1, 1, 1),
        "exported": kwh(0, 0, 0, 0),
        "self_consumed": kwh(0, 0, 0, 0),
    }
    with pytest.raises(FlowError, match=message):
        SiteFlows(**(fields | arguments))  # pyright: ignore[reportArgumentType]  # parametrised keyword arguments


def test_building_from_powers_needs_kw_on_one_grid() -> None:
    with pytest.raises(FlowError, match="no asset power"):
        SiteFlows.from_powers("home", [])
    with pytest.raises(FlowError, match="must be kW on one grid"):
        SiteFlows.from_powers("home", [kw(1, 1, 1, 1), kwh(1, 1, 1, 1)])
