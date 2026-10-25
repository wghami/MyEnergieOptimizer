"""Time-of-use schedules: user-defined periods by time of day, day type and season.

A ``Schedule`` names **periods** (``"HC"``, ``"super-off-peak"``, ``"HPH"``, …) and says, with
``PeriodRule`` values, which instants belong to each: daily time windows, optionally only on some
day types (``"sat"``, ``"weekend"``, or labels such as a Tempo colour from a ``DayCalendar``) and
in some seasons. Whatever no rule claims goes to the season's default period, else the schedule's
default. Every instant belongs to **exactly one** period: two rules that claim the same instant,
or an instant that nothing claims, are errors that name the instant.

Rules are applied **per instant**: a window is laid on every local day, then kept only where the
instant's own local date has the rule's day type and season. So ``22:00-06:00`` limited to
``"sat"`` covers Saturday 00:00-06:00 and 22:00-24:00.

``weights(grid)`` gives the **share** of each step in each period. Shares are exact: a step that
straddles a window edge is split by time, so energy split by period adds up to the total on any
grid. Shares are worked out in UTC, so daylight-saving days need no special case: a window
02:00-07:00 lasts 4 real hours on the spring day and 6 on the autumn day. A wall-clock time that
does not exist (02:30 on the spring day) is read with the offset in force before the change, as
Python does (PEP 495).
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from itertools import combinations
from typing import Protocol
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt

from myenergy.domain.errors import ScheduleError, SeriesError
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid

_DAY_MINUTES = 24 * 60
_WINDOW = re.compile(r"(\d{1,2})[:hH](\d{2})\s*-\s*(\d{1,2})[:hH](\d{2})")
_SEASON = re.compile(r"^(\d{2})-(\d{2})\s*\.\.\s*(\d{2})-(\d{2})$")
_TOLERANCE = 1e-6
"""Seconds below which a share is rounding noise, not a real overlap or gap."""
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_SATURDAY = WEEKDAY_NAMES.index("sat")
_LEAP_YEAR = 2024
"""Every month-day exists in a leap year."""


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """From ``start`` to ``end`` on the wall clock; it may run past midnight."""

    start: time
    end: time

    def __post_init__(self) -> None:
        """Check the window.

        Raises:
            ScheduleError: an empty window, seconds, or a timezone on the times.
        """
        for moment in (self.start, self.end):
            if moment.tzinfo is not None or moment.second or moment.microsecond:
                msg = f"window times are whole minutes on the wall clock, got {moment}"
                raise ScheduleError(msg)
        if self.start == self.end:
            msg = f"the window {self} is empty; leave the windows out for a whole day"
            raise ScheduleError(msg)

    @property
    def minutes(self) -> int:
        """Length in minutes on the wall clock."""
        return (_minute(self.end) - _minute(self.start)) % _DAY_MINUTES

    def __str__(self) -> str:
        """``HH:MM-HH:MM``."""
        return f"{self.start:%H:%M}-{self.end:%H:%M}"


def _minute(moment: time) -> int:
    return moment.hour * 60 + moment.minute


def _minutes_of_day(window: TimeWindow) -> set[int]:
    first = _minute(window.start)
    return {(first + offset) % _DAY_MINUTES for offset in range(window.minutes)}


@dataclass(frozen=True, slots=True)
class TimeWindows:
    """Daily windows that do not overlap, for example a connection's off-peak hours."""

    windows: tuple[TimeWindow, ...] = ()

    def __post_init__(self) -> None:
        """Sort the windows.

        Raises:
            ScheduleError: two windows overlap.
        """
        ordered = tuple(sorted(self.windows, key=lambda window: window.start))
        seen: set[int] = set()
        for window in ordered:
            minutes = _minutes_of_day(window)
            if seen & minutes:
                msg = f"windows overlap: {', '.join(str(w) for w in ordered)}"
                raise ScheduleError(msg)
            seen |= minutes
        object.__setattr__(self, "windows", ordered)

    @classmethod
    def parse(cls, text: str) -> "TimeWindows":
        """Read windows as written on a contract or a bill.

        ``"02:00-07:00 12:30-15:30"``, ``"2H00-7H00 12H30-15H30"`` and ``"22h30-6h30"`` are all
        accepted; spaces, commas, ``;`` and ``/`` between windows are ignored. ``""`` is no window.

        Raises:
            ScheduleError: unreadable text, or an hour or minute out of range.
        """
        windows: list[TimeWindow] = []
        for match in _WINDOW.finditer(text):
            h1, m1, h2, m2 = (int(part) for part in match.groups())
            try:
                windows.append(TimeWindow(time(h1 % 24, m1), time(h2 % 24, m2)))
            except ValueError:
                msg = f"invalid window {match.group(0)!r}"
                raise ScheduleError(msg) from None
        if _WINDOW.sub("", text).strip(" ,;/\t"):
            msg = f"cannot read time windows from {text!r}; write e.g. '02:00-07:00 12:30-15:30'"
            raise ScheduleError(msg)
        return cls(tuple(windows))

    @property
    def hours(self) -> float:
        """Hours covered on a normal day."""
        return sum(window.minutes for window in self.windows) / 60

    def __str__(self) -> str:
        """``HH:MM-HH:MM HH:MM-HH:MM``, or ``none``."""
        return " ".join(str(window) for window in self.windows) or "none"


NO_WINDOWS = TimeWindows()


@dataclass(frozen=True, slots=True)
class Season:
    """Local dates from ``first`` to ``last`` (``(month, day)``, inclusive; may wrap the year)."""

    name: str
    first: tuple[int, int]
    last: tuple[int, int]
    default: str | None = None
    """The period of instants in this season that no rule claims (else the schedule's default)."""

    def __post_init__(self) -> None:
        """Check the dates.

        Raises:
            ScheduleError: an empty name or an impossible date.
        """
        if not self.name:
            msg = "a season needs a name"
            raise ScheduleError(msg)
        for month, day in (self.first, self.last):
            try:
                date(_LEAP_YEAR, month, day)
            except ValueError:
                msg = f"season {self.name!r}: {month:02}-{day:02} is not a date"
                raise ScheduleError(msg) from None

    @classmethod
    def parse(cls, name: str, text: str, default: str | None = None) -> "Season":
        """``Season.parse("winter", "11-01..03-31")``.

        Raises:
            ScheduleError: the text is not ``MM-DD..MM-DD``.
        """
        match = _SEASON.match(text.strip())
        if match is None:
            msg = f"season {name!r}: write dates as 'MM-DD..MM-DD', got {text!r}"
            raise ScheduleError(msg)
        m1, d1, m2, d2 = (int(group) for group in match.groups())
        return cls(name, (m1, d1), (m2, d2), default)

    def contains(self, day: date) -> bool:
        """Whether ``day`` falls in the season."""
        key = (day.month, day.day)
        if self.first <= self.last:
            return self.first <= key <= self.last
        return key >= self.first or key <= self.last


class DayCalendar(Protocol):
    """Labels each local date (weekday names, a Tempo colour, ``"holiday"``, …)."""

    @property
    def vocabulary(self) -> frozenset[str]:
        """Every label this calendar can give; rules may only use these."""
        ...

    def labels(self, day: date) -> frozenset[str]:
        """The labels of ``day``."""
        ...


class WeekdayCalendar:
    """``"mon"`` … ``"sun"``, plus ``"weekday"`` or ``"weekend"``."""

    vocabulary = frozenset((*WEEKDAY_NAMES, "weekday", "weekend"))

    def labels(self, day: date) -> frozenset[str]:
        """The weekday name and whether it is a weekday or the weekend."""
        index = day.weekday()
        return frozenset((WEEKDAY_NAMES[index], "weekend" if index >= _SATURDAY else "weekday"))


WEEKDAYS = WeekdayCalendar()


@dataclass(frozen=True, slots=True)
class PeriodRule:
    """Instants of ``period``: in ``windows`` (all day if ``None``), on ``days``, in ``seasons``."""

    period: str
    windows: TimeWindows | None = None
    days: frozenset[str] | None = None
    """Day labels from the ``DayCalendar``; ``None`` is every day."""
    seasons: frozenset[str] | None = None
    """Season names of the schedule; ``None`` is every season."""

    def __post_init__(self) -> None:
        """Check the rule.

        Raises:
            ScheduleError: no period name, or an empty set of days or seasons.
        """
        if not self.period:
            msg = "a rule needs a period name"
            raise ScheduleError(msg)
        for name, chosen in (("days", self.days), ("seasons", self.seasons)):
            if chosen is not None and not chosen:
                msg = f"rule {self.period!r}: an empty set of {name} matches nothing; leave it out"
                raise ScheduleError(msg)

    def __str__(self) -> str:
        """The period and its conditions."""
        parts = [self.period]
        if self.windows is not None:
            parts.append(str(self.windows))
        if self.days is not None:
            parts.append("days " + ",".join(sorted(self.days)))
        if self.seasons is not None:
            parts.append("seasons " + ",".join(sorted(self.seasons)))
        return " ".join(parts)


type _Intervals = list[tuple[float, float]]
"""Disjoint, sorted ``[start, end)`` intervals in UTC seconds."""


def _instant(day: date, moment: time, zone: ZoneInfo) -> float:
    return datetime.combine(day, moment, tzinfo=zone).timestamp()


def _union(intervals: Iterable[tuple[float, float]]) -> _Intervals:
    merged: _Intervals = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _intersection(first: _Intervals, second: _Intervals) -> _Intervals:
    found: _Intervals = []
    i = j = 0
    while i < len(first) and j < len(second):
        start = max(first[i][0], second[j][0])
        end = min(first[i][1], second[j][1])
        if start < end:
            found.append((start, end))
        if first[i][1] < second[j][1]:
            i += 1
        else:
            j += 1
    return found


def _seconds_inside(
    intervals: _Intervals, edges: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Seconds of each step ``[edges[k], edges[k + 1])`` that fall inside ``intervals``."""
    if not intervals:
        return np.zeros(len(edges) - 1)
    points = np.array([bound for interval in intervals for bound in interval])
    lengths = np.array([end - start for start, end in intervals])
    inside = np.concatenate([[0.0], np.repeat(np.cumsum(lengths), 2)[:-1]])
    return np.diff(np.interp(edges, points, inside))


@dataclass(frozen=True, slots=True)
class PeriodWeights:
    """The share of each step in each period of a schedule; every row sums to 1."""

    grid: TimeGrid
    periods: tuple[str, ...]
    shares: npt.NDArray[np.float64] = field(repr=False)
    """Shape ``(len(grid), len(periods))``, columns in ``periods`` order."""

    def _column(self, period: str) -> int:
        try:
            return self.periods.index(period)
        except ValueError:
            msg = f"no period {period!r} (periods: {', '.join(self.periods)})"
            raise ScheduleError(msg) from None

    def share(self, period: str) -> TimeSeries:
        """The share of each step in ``period`` (dimensionless, 0 to 1).

        Raises:
            ScheduleError: the schedule has no such period.
        """
        column = self.shares[:, self._column(period)]
        return TimeSeries(grid=self.grid, values=column.copy(), quantity=Quantity.DIMENSIONLESS)

    def split(self, series: TimeSeries) -> Mapping[str, float]:
        """Energy (kWh) of a power or energy series in each period; the values add up to its total.

        Raises:
            SeriesError: the series is on another grid, or is neither power nor energy.
        """
        if series.grid != self.grid:
            msg = "the series and the schedule weights are on different grids"
            raise SeriesError(msg)
        if series.quantity not in {Quantity.POWER_KW, Quantity.ENERGY_KWH}:
            msg = f"only power or energy can be split by period, not {series.quantity.value}"
            raise SeriesError(msg)
        energy = series.energy() if series.quantity is Quantity.POWER_KW else series
        totals = energy.values @ self.shares
        return {period: float(total) for period, total in zip(self.periods, totals, strict=True)}


@dataclass(frozen=True, slots=True)
class Schedule:
    """Named periods defined by rules, seasons and defaults; see the module docstring."""

    name: str
    rules: tuple[PeriodRule, ...] = ()
    default: str | None = None
    """The period of instants no rule claims, in seasons without their own default."""
    seasons: tuple[Season, ...] = ()
    """When given, every date of the year must fall in exactly one season."""

    def __post_init__(self) -> None:
        """Check names, seasons and references.

        Raises:
            ScheduleError: an empty name, seasons that do not cover the year exactly once, or a
                rule that names an undeclared season.
        """
        if not self.name:
            msg = "a schedule needs a name"
            raise ScheduleError(msg)
        names = [season.name for season in self.seasons]
        if len(set(names)) != len(names):
            msg = f"schedule {self.name!r} repeats a season: {names}"
            raise ScheduleError(msg)
        if self.seasons:
            day = date(_LEAP_YEAR, 1, 1)
            while day.year == _LEAP_YEAR:
                found = [season.name for season in self.seasons if season.contains(day)]
                if len(found) != 1:
                    which = ", ".join(found) or "no season"
                    msg = (
                        f"schedule {self.name!r}: {day:%m-%d} falls in {which}; "
                        "seasons must cover each date once"
                    )
                    raise ScheduleError(msg)
                day += timedelta(days=1)
        for rule in self.rules:
            unknown = (rule.seasons or frozenset()) - set(names)
            if unknown:
                msg = f"schedule {self.name!r}: rule {rule} names unknown seasons {sorted(unknown)}"
                raise ScheduleError(msg)

    @property
    def periods(self) -> tuple[str, ...]:
        """Every period, rules first (in order), then defaults."""
        found = [rule.period for rule in self.rules]
        found += [season.default for season in self.seasons if season.default is not None]
        if self.default is not None:
            found.append(self.default)
        return tuple(dict.fromkeys(found))

    def _season_intervals(self, days: list[date], zone: ZoneInfo) -> dict[str, _Intervals]:
        return {
            season.name: _union(
                (_instant(day, time(), zone), _instant(day + timedelta(days=1), time(), zone))
                for day in days
                if season.contains(day)
            )
            for season in self.seasons
        }

    def _rule_intervals(
        self,
        rule: PeriodRule,
        days: list[date],
        zone: ZoneInfo,
        calendar: DayCalendar,
        seasons: Mapping[str, _Intervals],
    ) -> _Intervals:
        whole = [
            (_instant(days[0], time(), zone), _instant(days[-1] + timedelta(days=1), time(), zone))
        ]
        found = whole
        if rule.windows is not None:
            found = _union(
                (
                    _instant(day, window.start, zone),
                    _instant(day + timedelta(days=window.end <= window.start), window.end, zone),
                )
                for day in days
                for window in rule.windows.windows
            )
        if rule.days is not None:
            chosen = rule.days
            on_days = _union(
                (_instant(day, time(), zone), _instant(day + timedelta(days=1), time(), zone))
                for day in days
                if calendar.labels(day) & chosen
            )
            found = _intersection(found, on_days)
        if rule.seasons is not None:
            in_seasons = _union(interval for name in rule.seasons for interval in seasons[name])
            found = _intersection(found, in_seasons)
        return found

    def _check_days(self, calendar: DayCalendar) -> None:
        for rule in self.rules:
            unknown = (rule.days or frozenset()) - calendar.vocabulary
            if unknown:
                known = ", ".join(sorted(calendar.vocabulary))
                msg = (
                    f"schedule {self.name!r}: rule {rule} uses unknown days {sorted(unknown)} "
                    f"(known: {known})"
                )
                raise ScheduleError(msg)

    def _check_overlaps(
        self, claimed: list[_Intervals], edges: npt.NDArray[np.float64], zone: ZoneInfo
    ) -> None:
        for (one, ones), (two, twos) in combinations(zip(self.rules, claimed, strict=True), 2):
            both = _intersection(ones, twos)
            if _seconds_inside(both, edges).sum() > _TOLERANCE:
                moment = datetime.fromtimestamp(both[0][0], zone)
                msg = (
                    f"schedule {self.name!r}: rules {one} and {two} both claim "
                    f"{moment:%Y-%m-%d %H:%M %Z}"
                )
                raise ScheduleError(msg)

    def weights(self, grid: TimeGrid, calendar: DayCalendar = WEEKDAYS) -> PeriodWeights:
        """The share of each step of ``grid`` in each period, on the grid's wall clock.

        ``calendar`` labels the days (default: weekday names); a Tempo-like offer passes a
        calendar that also gives each day its colour.

        Raises:
            ScheduleError: a rule uses a day label the calendar does not know, two rules claim
                the same instant, or an instant has no period.
        """
        self._check_days(calendar)
        zone = grid.timezone
        first = grid.start.astimezone(zone).date() - timedelta(days=1)
        last = grid.end.astimezone(zone).date() + timedelta(days=1)
        days = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
        seasons = self._season_intervals(days, zone)
        claimed = [self._rule_intervals(rule, days, zone, calendar, seasons) for rule in self.rules]
        edges = grid.start.timestamp() + grid.edges_seconds()
        self._check_overlaps(claimed, edges, zone)
        periods = self.periods
        seconds = np.zeros((len(grid), len(periods)))
        for rule, intervals in zip(self.rules, claimed, strict=True):
            seconds[:, periods.index(rule.period)] += _seconds_inside(intervals, edges)
        taken = _union(interval for intervals in claimed for interval in intervals)
        parts = [(season.default or self.default, seasons[season.name]) for season in self.seasons]
        if not self.seasons:
            parts = [(self.default, [(edges[0], edges[-1])])]
        for default, inside in parts:
            rest = _seconds_inside(inside, edges)
            rest -= _seconds_inside(_intersection(inside, taken), edges)
            if default is not None:
                seconds[:, periods.index(default)] += rest
            elif rest.max(initial=0.0) > _TOLERANCE:
                moment = grid.local(int(np.argmax(rest > _TOLERANCE)))
                msg = (
                    f"schedule {self.name!r} gives no period to {moment:%Y-%m-%d %H:%M %Z}; "
                    "add a default"
                )
                raise ScheduleError(msg)
        return PeriodWeights(grid=grid, periods=periods, shares=seconds / grid.step.total_seconds())
