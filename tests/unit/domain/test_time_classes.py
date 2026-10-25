"""The network's four time classes are one built-in schedule."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from myenergy.domain.schedules import TimeWindows
from myenergy.domain.time import TimeGrid
from myenergy.domain.time_classes import (
    HIGH_SEASON,
    LOW_SEASON,
    TimeClass,
    network_schedule,
    turpe_seasons,
)

PARIS = ZoneInfo("Europe/Paris")
START = datetime(2026, 3, 31, tzinfo=PARIS)
TWO_DAYS = TimeGrid(start=START, end=START + timedelta(days=2), step=timedelta(hours=1))


def classes(schedule_hours: TimeWindows, low: TimeWindows | None = None) -> list[str]:
    weights = network_schedule(schedule_hours, low).weights(TWO_DAYS)
    return [weights.periods[int(index)] for index in weights.shares.argmax(axis=1)]


def test_seasons_change_at_local_midnight() -> None:
    found = classes(TimeWindows.parse("22:00-06:00"))
    assert found[:6] == [TimeClass.HCH] * 6
    assert found[6:22] == [TimeClass.HPH] * 16
    assert found[22:24] == [TimeClass.HCH] * 2
    assert found[24:30] == [TimeClass.HCB] * 6  # the night window carries over into April
    assert found[30:46] == [TimeClass.HPB] * 16


def test_off_peak_hours_may_differ_by_season() -> None:
    found = classes(TimeWindows.parse("22:00-06:00"), TimeWindows.parse("02:00-06:00 11:00-15:00"))
    assert found[24:26] == [TimeClass.HPB] * 2
    assert found[26:30] == [TimeClass.HCB] * 4
    assert found[35:39] == [TimeClass.HCB] * 4


def test_without_off_peak_hours_every_instant_is_peak() -> None:
    found = classes(TimeWindows())
    assert set(found[:24]) == {TimeClass.HPH}
    assert set(found[24:]) == {TimeClass.HPB}


def test_turpe_seasons() -> None:
    high, low = turpe_seasons({HIGH_SEASON: "x"})
    assert (high.name, high.first, high.last, high.default) == (HIGH_SEASON, (11, 1), (3, 31), "x")
    assert (low.name, low.first, low.last, low.default) == (LOW_SEASON, (4, 1), (10, 31), None)


def test_period_names_are_plain_text() -> None:
    periods = network_schedule(TimeWindows.parse("22:00-06:00")).periods
    assert periods == ("HCH", "HCB", "HPH", "HPB")
    assert all(type(period) is str for period in periods)
