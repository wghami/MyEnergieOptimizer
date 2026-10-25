"""Resampling conserves energy and time-weighted means, for any pair of supported steps."""

from datetime import UTC, datetime, timedelta

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import ALLOWED_STEPS, TimeGrid

START = datetime(2026, 10, 25, tzinfo=UTC)  # spans the autumn daylight-saving change in Paris
SPAN = timedelta(hours=6)  # a multiple of every allowed step


@st.composite
def series(draw: st.DrawFn, quantity: Quantity) -> TimeSeries:
    step = draw(st.sampled_from(ALLOWED_STEPS))
    grid = TimeGrid(start=START, end=START + SPAN, step=step)
    values = draw(
        st.lists(st.floats(min_value=-1e3, max_value=1e3), min_size=len(grid), max_size=len(grid))
    )
    return TimeSeries(grid=grid, values=np.array(values), quantity=quantity)


steps = st.sampled_from(ALLOWED_STEPS)


@settings(max_examples=200)
@given(series(Quantity.ENERGY_KWH), steps)
def test_energy_is_conserved(source: TimeSeries, step: timedelta) -> None:
    target = source.resample(source.grid.with_step(step))
    assert np.isclose(target.total(), source.total(), rtol=1e-9, atol=1e-6)


@settings(max_examples=200)
@given(series(Quantity.POWER_KW), steps)
def test_time_weighted_mean_is_conserved(source: TimeSeries, step: timedelta) -> None:
    target = source.resample(source.grid.with_step(step))
    assert np.isclose(target.time_mean(), source.time_mean(), rtol=1e-9, atol=1e-9)


@settings(max_examples=200)
@given(series(Quantity.POWER_KW), steps)
def test_refining_then_coarsening_is_exact(source: TimeSeries, step: timedelta) -> None:
    finer = min(step, source.grid.step)
    if source.grid.step % finer:
        return  # only exact refinements round-trip
    back = source.resample(source.grid.with_step(finer)).resample(source.grid)
    assert back.isclose(source, rel=1e-9, abs_=1e-9)


@given(series(Quantity.POWER_KW))
def test_energy_of_resampled_power_matches(source: TimeSeries) -> None:
    hourly = source.resample(source.grid.with_step(timedelta(hours=1)))
    assert np.isclose(hourly.energy().total(), source.energy().total(), rtol=1e-9, atol=1e-6)
