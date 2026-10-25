"""Schedules: user-defined periods by window, day and season, split exactly per step."""

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from myenergy.domain.errors import ScheduleError, SeriesError
from myenergy.domain.schedules import (
    NO_WINDOWS,
    WEEKDAYS,
    PeriodRule,
    Schedule,
    Season,
    TimeWindow,
    TimeWindows,
)
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid

PARIS = ZoneInfo("Europe/Paris")
SPLIT = TimeWindows.parse("01:30-07:30 13:30-15:30")
WINTER = Season.parse("winter", "11-01..03-31")
SUMMER = Season.parse("summer", "04-01..10-31")


def grid(start: datetime, days: int = 1, minutes: int = 60) -> TimeGrid:
    return TimeGrid(start=start, end=start + timedelta(days=days), step=timedelta(minutes=minutes))


def local(month: int, day: int, year: int = 2026) -> datetime:
    return datetime(year, month, day, tzinfo=PARIS)


def hp_hc(windows: TimeWindows = SPLIT) -> Schedule:
    return Schedule(name="hp-hc", rules=(PeriodRule("HC", windows),), default="HP")


def labels(schedule: Schedule, on: TimeGrid) -> list[str]:
    weights = schedule.weights(on)
    return [
        "/".join(p for p, s in zip(weights.periods, row, strict=True) if s > 0)
        for row in weights.shares
    ]


# --- windows ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "01:30-07:30 13:30-15:30",
        "1H30-7H30 13H30-15H30",
        "13h30-15h30, 1h30 - 7h30",
        "01:30-07:30; 13:30-15:30 /",
    ],
)
def test_windows_are_read_as_written_on_bills(text: str) -> None:
    windows = TimeWindows.parse(text)
    assert windows == SPLIT
    assert str(windows) == "01:30-07:30 13:30-15:30"
    assert windows.hours == 8


def test_windows_may_run_past_midnight_or_be_absent() -> None:
    assert TimeWindows.parse("22h30-6h30").windows == (TimeWindow(time(22, 30), time(6, 30)),)
    assert TimeWindows.parse("24:00-08:00").windows[0].start == time(0)
    assert TimeWindows.parse("") == NO_WINDOWS
    assert str(NO_WINDOWS) == "none"
    assert NO_WINDOWS.hours == 0


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("from 2 to 7", "cannot read"),
        ("02:00-07:00 and noon", "cannot read"),
        ("02:00-07:61", "invalid window"),
        ("02:00-02:00", "empty"),
        ("22:00-06:00 05:00-07:00", "overlap"),
    ],
)
def test_unreadable_or_overlapping_windows_are_refused(text: str, message: str) -> None:
    with pytest.raises(ScheduleError, match=message):
        TimeWindows.parse(text)


def test_windows_are_whole_minutes_on_the_wall_clock() -> None:
    with pytest.raises(ScheduleError, match="whole minutes"):
        TimeWindow(time(2, 0, 30), time(7))
    with pytest.raises(ScheduleError, match="whole minutes"):
        TimeWindow(time(2, tzinfo=PARIS), time(7))


# --- seasons, days, rules ----------------------------------------------------------------------


def test_seasons_may_wrap_the_year() -> None:
    assert WINTER.contains(date(2026, 12, 31))
    assert WINTER.contains(date(2026, 3, 31))
    assert not WINTER.contains(date(2026, 4, 1))
    assert SUMMER.contains(date(2026, 7, 14))
    assert not SUMMER.contains(date(2026, 11, 1))
    assert Season.parse("x", " 02-29 .. 03-01 ", "p").default == "p"


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: Season.parse("x", "11-01"), "MM-DD..MM-DD"),
        (lambda: Season.parse("x", "13-01..03-31"), "13-01 is not a date"),
        (lambda: Season("", (1, 1), (12, 31)), "needs a name"),
        (lambda: PeriodRule(""), "needs a period name"),
        (lambda: PeriodRule("p", days=frozenset()), "empty set of days"),
        (lambda: Schedule(name=""), "needs a name"),
        (lambda: Schedule(name="s", seasons=(WINTER, WINTER)), "repeats a season"),
        (lambda: Schedule(name="s", seasons=(WINTER,)), "04-01 falls in no season"),
        (
            lambda: Schedule(name="s", seasons=(WINTER, Season.parse("all", "01-01..12-31"))),
            "falls in winter, all",
        ),
        (
            lambda: Schedule(name="s", rules=(PeriodRule("p", seasons=frozenset({"winter"})),)),
            "unknown seasons",
        ),
    ],
)
def test_malformed_definitions_are_refused(make: Callable[[], object], message: str) -> None:
    with pytest.raises(ScheduleError, match=message):
        make()


def test_weekday_labels() -> None:
    assert WEEKDAYS.labels(date(2026, 1, 10)) == {"sat", "weekend"}
    assert WEEKDAYS.labels(date(2026, 1, 12)) == {"mon", "weekday"}
    assert str(PeriodRule("p", SPLIT, frozenset({"sun", "sat"}), frozenset({"winter"}))) == (
        "p 01:30-07:30 13:30-15:30 days sat,sun seasons winter"
    )


# --- weights -----------------------------------------------------------------------------------


def test_whole_steps_take_one_period() -> None:
    assert labels(hp_hc(), grid(local(1, 15), minutes=30)) == (
        ["HP"] * 3 + ["HC"] * 12 + ["HP"] * 12 + ["HC"] * 4 + ["HP"] * 17
    )


def test_a_step_across_a_window_edge_is_split_by_time() -> None:
    weights = hp_hc().weights(grid(local(1, 15)))
    assert weights.periods == ("HC", "HP")
    assert weights.shares[1].tolist() == [0.5, 0.5]  # 01:00-02:00, off-peak from 01:30
    assert weights.shares[13].tolist() == [0.5, 0.5]
    assert weights.share("HP").quantity is Quantity.DIMENSIONLESS


@pytest.mark.parametrize(("month", "day", "steps", "off_peak"), [(3, 29, 92, 7), (10, 25, 100, 9)])
def test_daylight_saving_days(month: int, day: int, steps: int, off_peak: int) -> None:
    """02:00 does not exist on the spring day, and occurs twice on the autumn day."""
    weights = hp_hc(TimeWindows.parse("02:00-07:00 12:00-15:00")).weights(
        grid(local(month, day), minutes=15)
    )
    assert len(weights.grid) == steps
    split = weights.split(TimeSeries.constant(weights.grid, 1.0, Quantity.POWER_KW))
    assert split["HC"] == pytest.approx(off_peak)
    assert sum(split.values()) == pytest.approx(steps / 4)


def test_days_and_seasons_are_read_per_instant() -> None:
    """A night window limited to Saturday covers Saturday's early and late hours only."""
    schedule = Schedule(
        name="weekend-nights",
        rules=(PeriodRule("night", TimeWindows.parse("22:00-06:00"), days=frozenset({"sat"})),),
        default="day",
    )
    friday_to_sunday = labels(schedule, grid(local(1, 9), days=3))  # 2026-01-09 is a Friday
    assert friday_to_sunday[:24] == ["day"] * 24
    assert friday_to_sunday[24:48] == ["night"] * 6 + ["day"] * 16 + ["night"] * 2
    assert friday_to_sunday[48:] == ["day"] * 24


def test_each_season_may_have_its_own_default_and_windows() -> None:
    schedule = Schedule(
        name="seasonal",
        rules=(
            PeriodRule("HC", TimeWindows.parse("22:00-06:00"), seasons=frozenset({"winter"})),
            PeriodRule(
                "HC", TimeWindows.parse("11:00-17:00 02:00-04:00"), seasons=frozenset({"summer"})
            ),
        ),
        seasons=(Season("winter", (11, 1), (3, 31), "HP-winter"), SUMMER),
        default="HP",
    )
    two_days = labels(schedule, grid(local(3, 31), days=2))
    assert two_days[:6] == ["HC"] * 6
    assert two_days[6:22] == ["HP-winter"] * 16
    assert two_days[24:26] == ["HP"] * 2  # 1 April: the winter night window no longer applies
    assert two_days[26:28] == ["HC"] * 2
    assert two_days[35:41] == ["HC"] * 6
    assert schedule.periods == ("HC", "HP-winter", "HP")


def test_any_number_of_periods() -> None:
    schedule = Schedule(
        name="four-windows",
        rules=tuple(
            PeriodRule(name, TimeWindows.parse(text))
            for name, text in (
                ("night", "00:00-06:00"),
                ("morning", "06:00-12:00"),
                ("afternoon", "12:00-18:00"),
            )
        ),
        default="evening",
    )
    weights = schedule.weights(grid(local(6, 1)))
    assert weights.periods == ("night", "morning", "afternoon", "evening")
    assert weights.shares.sum(axis=0).tolist() == [6, 6, 6, 6]


def test_a_single_period_schedule() -> None:
    weights = Schedule(name="base", default="base").weights(grid(local(7, 1)))
    assert weights.periods == ("base",)
    assert weights.shares[:, 0].tolist() == [1.0] * 24


def test_two_rules_on_the_same_instant_are_refused() -> None:
    schedule = Schedule(
        name="clash",
        rules=(
            PeriodRule("night", TimeWindows.parse("22:00-06:00")),
            PeriodRule("weekend", days=frozenset({"weekend"})),
        ),
        default="day",
    )
    schedule.weights(grid(local(1, 7)))  # a Wednesday: no clash
    with pytest.raises(
        ScheduleError,
        match=r"night 22:00-06:00 and weekend days weekend both claim 2026-01-10 00:00 CET",
    ):
        schedule.weights(grid(local(1, 10)))


def test_instants_without_a_period_are_refused() -> None:
    with pytest.raises(
        ScheduleError, match="gives no period to 2026-01-15 00:00 CET; add a default"
    ):
        Schedule(name="gaps", rules=(PeriodRule("HC", SPLIT),)).weights(grid(local(1, 15)))
    seasonal = Schedule(
        name="gaps",
        rules=(PeriodRule("x", seasons=frozenset({"winter"})),),
        seasons=(WINTER, SUMMER),
    )
    seasonal.weights(grid(local(1, 15)))  # winter is fully claimed
    with pytest.raises(ScheduleError, match="2026-07-01 00:00 CEST"):
        seasonal.weights(grid(local(7, 1)))


class _Colours:
    """A test-only day calendar, like Tempo: weekday names plus a colour."""

    vocabulary = WEEKDAYS.vocabulary | {"blue", "red"}

    def labels(self, day: date) -> frozenset[str]:
        return WEEKDAYS.labels(day) | {"red" if day.day % 2 else "blue"}


def test_day_calendars_add_labels_such_as_colours() -> None:
    schedule = Schedule(
        name="tempo-like",
        rules=(PeriodRule("red-peak", TimeWindows.parse("06:00-22:00"), days=frozenset({"red"})),),
        default="normal",
    )
    weights = schedule.weights(grid(local(1, 15), days=2), _Colours())  # 15 red, 16 blue
    assert (
        weights.split(TimeSeries.constant(weights.grid, 1.0, Quantity.POWER_KW))["red-peak"] == 16
    )
    with pytest.raises(ScheduleError, match=r"unknown days \['red'\]"):
        schedule.weights(grid(local(1, 15)))


def test_split_adds_up_to_the_energy() -> None:
    day = grid(local(1, 15))
    weights = hp_hc().weights(day)
    power = TimeSeries(grid=day, values=np.arange(24, dtype=np.float64), quantity=Quantity.POWER_KW)
    by_period = weights.split(power)
    assert by_period == weights.split(power.energy())
    assert sum(by_period.values()) == pytest.approx(power.energy().total())


def test_split_needs_power_or_energy_on_the_same_grid() -> None:
    day = grid(local(1, 15))
    weights = hp_hc().weights(day)
    with pytest.raises(SeriesError, match="different grids"):
        weights.split(TimeSeries.constant(grid(local(1, 16)), 1.0, Quantity.POWER_KW))
    with pytest.raises(SeriesError, match="not EUR/kWh"):
        weights.split(TimeSeries.constant(day, 1.0, Quantity.PRICE_EUR_PER_KWH))
    with pytest.raises(ScheduleError, match=r"no period 'HPH' \(periods: HC, HP\)"):
        weights.share("HPH")
