"""Time classes split every step exactly between peak/off-peak and high/low season."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from myenergy.domain.errors import ContractError, SeriesError
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid
from myenergy.domain.time_classes import (
    NO_OFF_PEAK,
    OffPeakHours,
    OffPeakWindow,
    TimeClass,
    TimeClassCalendar,
)

PARIS = ZoneInfo("Europe/Paris")
SPLIT = OffPeakHours.parse("01:30-07:30 13:30-15:30")


def grid(start: datetime, days: int = 1, minutes: int = 60) -> TimeGrid:
    return TimeGrid(start=start, end=start + timedelta(days=days), step=timedelta(minutes=minutes))


def local(month: int, day: int, year: int = 2026) -> datetime:
    return datetime(year, month, day, tzinfo=PARIS)


@pytest.mark.parametrize(
    "text",
    [
        "01:30-07:30 13:30-15:30",
        "1H30-7H30 13H30-15H30",
        "13h30-15h30, 1h30 - 7h30",
        "01:30-07:30; 13:30-15:30 /",
    ],
)
def test_off_peak_hours_are_read_as_written_on_bills(text: str) -> None:
    hours = OffPeakHours.parse(text)
    assert hours == SPLIT
    assert str(hours) == "01:30-07:30 13:30-15:30"
    assert hours.hours == 8


def test_a_window_may_run_past_midnight() -> None:
    hours = OffPeakHours.parse("22h30-6h30")
    assert hours.windows == (OffPeakWindow(time(22, 30), time(6, 30)),)
    assert hours.hours == 8
    assert OffPeakHours.parse("24:00-08:00").windows[0].start == time(0)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "cannot read"),
        ("from 2 to 7", "cannot read"),
        ("02:00-07:00 and noon", "cannot read"),
        ("02:00-07:61", "invalid off-peak window"),
        ("02:00-02:00", "empty"),
        ("22:00-06:00 05:00-07:00", "overlap"),
    ],
)
def test_unreadable_or_inconsistent_hours_are_refused(text: str, message: str) -> None:
    with pytest.raises(ContractError, match=message):
        OffPeakHours.parse(text)


def test_windows_are_whole_minutes_on_the_wall_clock() -> None:
    with pytest.raises(ContractError, match="whole minutes"):
        OffPeakWindow(time(2, 0, 30), time(7))
    with pytest.raises(ContractError, match="whole minutes"):
        OffPeakWindow(time(2, tzinfo=PARIS), time(7))
    assert str(NO_OFF_PEAK) == "none"
    assert NO_OFF_PEAK.hours == 0


def test_whole_steps_take_one_class() -> None:
    weights = TimeClassCalendar(SPLIT).weights(grid(local(1, 15), minutes=30))
    hch = weights.share(TimeClass.HCH).values
    assert hch.tolist() == [0.0] * 3 + [1.0] * 12 + [0.0] * 12 + [1.0] * 4 + [0.0] * 17
    assert weights.shares[:, [2, 3]].sum() == 0
    assert weights.share(TimeClass.HPH).quantity is Quantity.DIMENSIONLESS


def test_a_step_across_a_window_edge_is_split_by_time() -> None:
    weights = TimeClassCalendar(SPLIT).weights(grid(local(1, 15)))
    assert weights.shares[1].tolist() == [0.5, 0.5, 0.0, 0.0]  # 01:00-02:00, HC from 01:30
    assert weights.shares[13].tolist() == [0.5, 0.5, 0.0, 0.0]  # 13:00-14:00, HC from 13:30


def test_seasons_change_at_local_midnight() -> None:
    weights = TimeClassCalendar(OffPeakHours.parse("22:00-06:00")).weights(
        grid(local(3, 31), days=2)
    )
    by_hour = [TimeClass(list(TimeClass)[int(np.argmax(row))]) for row in weights.shares]
    assert by_hour[:6] == [TimeClass.HCH] * 6
    assert by_hour[6:22] == [TimeClass.HPH] * 16
    assert by_hour[22:24] == [TimeClass.HCH] * 2
    assert by_hour[24:30] == [TimeClass.HCB] * 6  # the night window carries over into April
    assert by_hour[30:46] == [TimeClass.HPB] * 16


@pytest.mark.parametrize(("month", "day", "steps", "off_peak"), [(3, 29, 92, 7), (10, 25, 100, 9)])
def test_daylight_saving_days(month: int, day: int, steps: int, off_peak: int) -> None:
    """02:00 does not exist on the spring day, and occurs twice on the autumn day."""
    hours = OffPeakHours.parse("02:00-07:00 12:00-15:00")
    weights = TimeClassCalendar(hours).weights(grid(local(month, day), minutes=15))
    assert len(weights.grid) == steps
    split = weights.split(TimeSeries.constant(weights.grid, 1.0, Quantity.POWER_KW))
    assert split[TimeClass.HCH] + split[TimeClass.HCB] == pytest.approx(off_peak)
    assert sum(split.values()) == pytest.approx(steps / 4)


def test_without_off_peak_hours_every_step_is_peak() -> None:
    weights = TimeClassCalendar().weights(grid(local(7, 1)))
    assert weights.shares[:, 2].tolist() == [1.0] * 24


def test_seasons_can_be_redefined() -> None:
    weights = TimeClassCalendar(NO_OFF_PEAK, frozenset({7})).weights(grid(local(7, 1)))
    assert weights.shares[:, 0].tolist() == [1.0] * 24


def test_split_adds_up_to_the_energy() -> None:
    day = grid(local(1, 15))
    weights = TimeClassCalendar(SPLIT).weights(day)
    power = TimeSeries(grid=day, values=np.arange(24, dtype=np.float64), quantity=Quantity.POWER_KW)
    by_class = weights.split(power)
    assert by_class == weights.split(power.energy())
    assert sum(by_class.values()) == pytest.approx(power.energy().total())
    assert by_class[TimeClass.HPB] == 0


def test_split_needs_power_or_energy_on_the_same_grid() -> None:
    day = grid(local(1, 15))
    weights = TimeClassCalendar(SPLIT).weights(day)
    with pytest.raises(SeriesError, match="different grids"):
        weights.split(TimeSeries.constant(grid(local(1, 16)), 1.0, Quantity.POWER_KW))
    with pytest.raises(SeriesError, match="not EUR/kWh"):
        weights.split(TimeSeries.constant(day, 1.0, Quantity.PRICE_EUR_PER_KWH))
