"""Schedule shares partition every step, and agree across steps: energy is never lost."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.domain.schedules import TimeWindow, TimeWindows
from myenergy.domain.time import ALLOWED_STEPS, TimeGrid

PARIS = ZoneInfo("Europe/Paris")
FRANCE = TomlPackSource([builtin_packs()]).pack("fr-household")
FIELDS = {"fta": "LU", "supply_option": "base"}  # no off-peak check, so no warning


@st.composite
def off_peak(draw: st.DrawFn) -> TimeWindows:
    """One or two windows on half hours, disjoint on the clock."""
    starts = draw(st.lists(st.integers(0, 47), min_size=1, max_size=2, unique=True))
    first = min(starts)
    windows: list[TimeWindow] = []
    for index, start in enumerate(sorted(starts)):
        limit = [*sorted(starts), first + 48][index + 1]
        length = draw(st.integers(1, min(limit - start, 47)))
        end = (start + length) % 48
        windows.append(
            TimeWindow(time(start // 2, 30 * (start % 2)), time(end // 2, 30 * (end % 2)))
        )
    return TimeWindows(tuple(windows))


@st.composite
def grids(draw: st.DrawFn) -> TimeGrid:
    day = draw(st.dates(date(2025, 1, 1), date(2027, 12, 31)))
    start = datetime(day.year, day.month, day.day, tzinfo=PARIS)
    return TimeGrid(
        start=start, end=start + timedelta(days=draw(st.integers(1, 3))), step=timedelta(hours=1)
    )


@settings(max_examples=150)
@given(off_peak(), grids(), st.sampled_from(ALLOWED_STEPS))
def test_shares_partition_each_step_and_agree_across_steps(
    hours: TimeWindows, hourly: TimeGrid, step: timedelta
) -> None:
    schedule = FRANCE.network_schedule(
        FRANCE.contract(subscribed_kva=6, fields=FIELDS, off_peak=hours)
    )
    coarse = schedule.weights(hourly).shares
    fine = schedule.weights(hourly.with_step(step)).shares
    np.testing.assert_allclose(coarse.sum(axis=1), 1.0, atol=1e-12)
    assert coarse.min() >= -1e-12
    per_hour = int(timedelta(hours=1) / step)
    regrouped = fine.reshape(len(coarse), per_hour, 4).mean(axis=1)
    np.testing.assert_allclose(regrouped, coarse, atol=1e-12)
