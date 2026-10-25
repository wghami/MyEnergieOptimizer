"""Time grids: half-open UTC ranges of equal, aligned steps (SPEC §3, decision 8)."""

from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from myenergy.domain.errors import GridError
from myenergy.domain.time import ALLOWED_STEPS, DEFAULT_TIMEZONE, TimeGrid

PARIS = ZoneInfo("Europe/Paris")
Q = timedelta(minutes=15)


def utc(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=UTC)


def day(step: timedelta = Q) -> TimeGrid:
    return TimeGrid(start=utc(2026, 1, 1), end=utc(2026, 1, 2), step=step)


def test_allowed_steps_divide_an_hour() -> None:
    assert [s.total_seconds() / 60 for s in ALLOWED_STEPS] == [5, 10, 15, 20, 30, 60]


def test_a_day_of_quarter_hours() -> None:
    grid = day()
    assert len(grid) == 96
    assert grid.step_hours == 0.25
    assert grid.span == timedelta(days=1)
    assert grid.timezone is DEFAULT_TIMEZONE
    assert grid.timestamp(0) == utc(2026, 1, 1)
    assert grid.timestamp(-1) == utc(2026, 1, 1, 23, 45)
    assert list(grid)[:2] == [utc(2026, 1, 1), utc(2026, 1, 1, 0, 15)]
    assert grid.edges_seconds()[[0, -1]].tolist() == [0.0, 86_400.0]
    assert grid.edges_seconds().dtype == np.float64


def test_inputs_are_normalised_to_utc() -> None:
    paris_midnight = datetime(2026, 1, 1, tzinfo=PARIS)
    grid = TimeGrid(start=paris_midnight, end=paris_midnight + timedelta(hours=1), step=Q)
    assert grid.start == utc(2025, 12, 31, 23)
    assert grid.start.tzinfo is UTC
    assert TimeGrid.covering(utc(2026, 1, 1), utc(2026, 1, 2), Q) == day()


def test_local_wall_clock() -> None:
    assert day().local(0) == datetime(2026, 1, 1, 1, tzinfo=PARIS)


def test_daylight_saving_days_are_plain_utc_ranges() -> None:
    spring = TimeGrid(
        start=datetime(2026, 3, 29, tzinfo=PARIS), end=datetime(2026, 3, 30, tzinfo=PARIS), step=Q
    )
    autumn = TimeGrid(
        start=datetime(2026, 10, 25, tzinfo=PARIS), end=datetime(2026, 10, 26, tzinfo=PARIS), step=Q
    )
    assert len(spring) == 23 * 4
    assert len(autumn) == 25 * 4
    hours = [autumn.local(i).hour for i in range(0, len(autumn), 4)]
    assert hours[:4] == [0, 1, 2, 2]  # 02:00 happens twice on the wall clock


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start": datetime(2026, 1, 1)}, "start must be timezone-aware"),  # noqa: DTZ001  # naive on purpose
        ({"end": datetime(2026, 1, 2)}, "end must be timezone-aware"),  # noqa: DTZ001  # naive on purpose
        (
            {"step": timedelta(minutes=7)},
            "step 0:07:00 is not supported; use one of 5, 10, 15, 20, 30, 60 minutes",
        ),
        ({"end": utc(2026, 1, 1)}, "the grid is empty"),
        ({"start": utc(2026, 1, 1, 0, 5)}, "is not aligned on the 0:15:00 step"),
        ({"end": utc(2026, 1, 1, 23, 50)}, "is not a whole number of 0:15:00 steps"),
    ],
)
def test_invalid_grids_are_refused(kwargs: dict[str, object], message: str) -> None:
    arguments: dict[str, object] = {"start": utc(2026, 1, 1), "end": utc(2026, 1, 2), "step": Q}
    with pytest.raises(GridError, match=message):
        TimeGrid(**(arguments | kwargs))  # pyright: ignore[reportArgumentType]  # typed above


def test_index_of_a_moment() -> None:
    grid = day()
    assert grid.index(utc(2026, 1, 1, 10, 30)) == 42
    assert grid.index(datetime(2026, 1, 1, 11, 30, tzinfo=timezone(timedelta(hours=1)))) == 42
    with pytest.raises(GridError, match="is outside"):
        grid.index(utc(2026, 1, 2))
    with pytest.raises(GridError, match="is outside"):
        grid.index(utc(2025, 12, 31, 23, 45))
    with pytest.raises(GridError, match="is not a step boundary"):
        grid.index(utc(2026, 1, 1, 10, 31))
    with pytest.raises(GridError, match="moment must be timezone-aware"):
        grid.index(datetime(2026, 1, 1))  # noqa: DTZ001  # naive on purpose


def test_timestamp_bounds() -> None:
    with pytest.raises(GridError, match="step 96 is outside a grid of 96 steps"):
        day().timestamp(96)
    with pytest.raises(GridError, match="step -97 is outside"):
        day().timestamp(-97)


def test_sub_ranges_and_containment() -> None:
    grid = day()
    morning = grid.sub(utc(2026, 1, 1, 6), utc(2026, 1, 1, 12))
    assert (len(morning), morning.step, morning.timezone) == (24, Q, grid.timezone)
    assert grid.contains(morning)
    assert not morning.contains(grid)
    assert grid.contains(grid)
    with pytest.raises(GridError, match="is outside this grid"):
        grid.sub(utc(2026, 1, 1, 12), utc(2026, 1, 2, 1))
    with pytest.raises(GridError, match="is outside this grid"):
        grid.sub(utc(2025, 12, 31, 23), utc(2026, 1, 1, 1))


def test_with_step() -> None:
    hourly = day().with_step(timedelta(hours=1))
    assert (len(hourly), hourly.start, hourly.end) == (24, utc(2026, 1, 1), utc(2026, 1, 2))
    with pytest.raises(GridError, match="not aligned"):
        TimeGrid(start=utc(2026, 1, 1, 0, 15), end=utc(2026, 1, 1, 1, 15), step=Q).with_step(
            timedelta(hours=1)
        )


class _NoOffset(tzinfo):
    """A tzinfo that cannot say its offset: as ambiguous as a naive time."""

    def utcoffset(self, dt: datetime | None) -> None:
        del dt

    def dst(self, dt: datetime | None) -> None:
        del dt


def test_a_tzinfo_without_offset_is_naive() -> None:
    with pytest.raises(GridError, match="start must be timezone-aware"):
        TimeGrid(start=datetime(2026, 1, 1, tzinfo=_NoOffset()), end=utc(2026, 1, 2), step=Q)


def test_index_edges_and_types() -> None:
    grid = day()
    assert grid.index(utc(2026, 1, 1)) == 0
    assert type(grid.index(utc(2026, 1, 1, 0, 15))) is int
    assert grid.timestamp(-96) == utc(2026, 1, 1)
    with pytest.raises(
        GridError,
        match=(
            r"^2026-01-02T00:00:00\+00:00 is outside "
            r"\[2026-01-01T00:00:00\+00:00, 2026-01-02T00:00:00\+00:00\)$"
        ),
    ):
        grid.index(utc(2026, 1, 2))


def test_local_uses_the_grid_timezone() -> None:
    tokyo = ZoneInfo("Asia/Tokyo")
    grid = TimeGrid(start=utc(2026, 1, 1), end=utc(2026, 1, 2), step=Q, timezone=tokyo)
    assert grid.local(0).tzinfo is tokyo
    assert grid.local(0).hour == 9


def test_sub_and_with_step_keep_the_timezone() -> None:
    tokyo = ZoneInfo("Asia/Tokyo")
    grid = TimeGrid(start=utc(2026, 1, 1), end=utc(2026, 1, 2), step=Q, timezone=tokyo)
    assert grid.sub(utc(2026, 1, 1, 6), utc(2026, 1, 1, 12)).timezone is tokyo
    assert grid.with_step(timedelta(hours=1)).timezone is tokyo
