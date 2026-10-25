"""Flows built from asset powers balance, and coarser steps never show less self-consumption."""

from datetime import UTC, datetime, timedelta

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from myenergy.domain.flows import FlowKind, SiteFlows
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid

START = datetime(2026, 6, 1, tzinfo=UTC)
FINE = TimeGrid(start=START, end=START + timedelta(hours=2), step=timedelta(minutes=5))
COARSE = FINE.with_step(timedelta(minutes=30))
power = st.floats(min_value=0, max_value=10, allow_nan=False)


def series(values: list[float], sign: float) -> TimeSeries:
    return TimeSeries(grid=FINE, values=sign * np.array(values), quantity=Quantity.POWER_KW)


@given(
    st.lists(st.lists(power, min_size=len(FINE), max_size=len(FINE)), min_size=1, max_size=3),
    st.lists(st.lists(power, min_size=len(FINE), max_size=len(FINE)), min_size=1, max_size=3),
)
def test_balance_and_netting(sources: list[list[float]], sinks: list[list[float]]) -> None:
    powers = [series(v, 1.0) for v in sources] + [series(v, -1.0) for v in sinks]
    flows = SiteFlows.from_powers("site", powers)
    produced = sum(np.array(v) for v in sources) * FINE.step_hours
    consumed = sum(np.array(v) for v in sinks) * FINE.step_hours
    np.testing.assert_allclose(
        flows.self_consumed.values + flows.imported.values, consumed, atol=1e-9
    )
    np.testing.assert_allclose(
        flows.self_consumed.values + flows.exported.values, produced, atol=1e-9
    )
    assert min(flows.imported.values.min(), flows.exported.values.min()) >= 0
    assert not np.any((flows.imported.values > 0) & (flows.exported.values > 0))
    coarse = SiteFlows.from_powers("site", [p.resample(COARSE) for p in powers])
    fine_self = flows.totals()[FlowKind.SELF_CONSUMPTION]
    assert coarse.totals()[FlowKind.SELF_CONSUMPTION] >= fine_self - 1e-9
    assert np.isclose(
        coarse.totals()[FlowKind.IMPORT] - coarse.totals()[FlowKind.EXPORT],
        flows.totals()[FlowKind.IMPORT] - flows.totals()[FlowKind.EXPORT],
    )
