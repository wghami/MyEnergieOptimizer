"""Time classes: which share of each step is peak or off-peak, in the high or the low season.

The network tariff prices energy by four classes (TURPE): peak and off-peak hours (HP/HC) of the
high season (November to March) and of the low season (April to October). Off-peak hours belong
to each connection and are read on the local wall clock; seasons follow the local date.

Shares are **exact**: a step that straddles a boundary (a 60-minute step over a 12:30 window
edge) is split by time, so energy split by class always adds up to the total. Shares are worked
out in UTC, so daylight-saving days need no special case: a window 02:00-07:00 lasts 4 real hours
on the spring day and 6 on the autumn day. A wall-clock time that does not exist (02:30 on the
spring day) is read with the offset in force before the change, as Python does (PEP 495).
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt

from myenergy.domain.errors import ContractError, SeriesError
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid

HIGH_SEASON_MONTHS = frozenset({11, 12, 1, 2, 3})
"""TURPE high season: November to March inclusive."""
_DAY_MINUTES = 24 * 60
_WINDOW = re.compile(r"(\d{1,2})[:hH](\d{2})\s*-\s*(\d{1,2})[:hH](\d{2})")


class TimeClass(StrEnum):
    """The four TURPE time classes, in the order of the published grids."""

    HPH = "HPH"
    """Peak hours, high season."""
    HCH = "HCH"
    """Off-peak hours, high season."""
    HPB = "HPB"
    """Peak hours, low season."""
    HCB = "HCB"
    """Off-peak hours, low season."""


CLASSES = tuple(TimeClass)


@dataclass(frozen=True, slots=True)
class OffPeakWindow:
    """Off-peak hours from ``start`` to ``end`` on the wall clock; it may run past midnight."""

    start: time
    end: time

    def __post_init__(self) -> None:
        """Check the window.

        Raises:
            ContractError: an empty window, seconds, or a timezone on the times.
        """
        for moment in (self.start, self.end):
            if moment.tzinfo is not None or moment.second or moment.microsecond:
                msg = f"off-peak times are whole minutes on the wall clock, got {moment}"
                raise ContractError(msg)
        if self.start == self.end:
            msg = f"the off-peak window {self} is empty"
            raise ContractError(msg)

    @property
    def minutes(self) -> int:
        """Length in minutes on the wall clock."""
        return (_minute(self.end) - _minute(self.start)) % _DAY_MINUTES

    def __str__(self) -> str:
        """``HH:MM-HH:MM``."""
        return f"{self.start:%H:%M}-{self.end:%H:%M}"


def _minute(moment: time) -> int:
    return moment.hour * 60 + moment.minute


def _minutes_of_day(window: OffPeakWindow) -> set[int]:
    first = _minute(window.start)
    return {(first + offset) % _DAY_MINUTES for offset in range(window.minutes)}


@dataclass(frozen=True, slots=True)
class OffPeakHours:
    """The off-peak windows of a connection; none at all for a flat (single-price) contract."""

    windows: tuple[OffPeakWindow, ...] = ()

    def __post_init__(self) -> None:
        """Sort the windows.

        Raises:
            ContractError: two windows overlap.
        """
        ordered = tuple(sorted(self.windows, key=lambda window: window.start))
        seen: set[int] = set()
        for window in ordered:
            minutes = _minutes_of_day(window)
            if seen & minutes:
                msg = f"off-peak windows overlap: {', '.join(str(w) for w in ordered)}"
                raise ContractError(msg)
            seen |= minutes
        object.__setattr__(self, "windows", ordered)

    @classmethod
    def parse(cls, text: str) -> "OffPeakHours":
        """Read windows as written on a contract or a bill.

        ``"02:00-07:00 12:30-15:30"``, ``"2H00-7H00 12H30-15H30"`` and ``"22h30-6h30"`` are all
        accepted; anything else between windows (spaces, commas, ``;``, ``/``) is ignored.

        Raises:
            ContractError: no window, or an hour or minute out of range.
        """
        windows: list[OffPeakWindow] = []
        for match in _WINDOW.finditer(text):
            h1, m1, h2, m2 = (int(part) for part in match.groups())
            try:
                windows.append(OffPeakWindow(time(h1 % 24, m1), time(h2 % 24, m2)))
            except ValueError:
                msg = f"invalid off-peak window {match.group(0)!r}"
                raise ContractError(msg) from None
        leftover = _WINDOW.sub("", text).strip(" ,;/\t")
        if not windows or leftover:
            msg = f"cannot read off-peak hours from {text!r}; write e.g. '02:00-07:00 12:30-15:30'"
            raise ContractError(msg)
        return cls(tuple(windows))

    @property
    def hours(self) -> float:
        """Off-peak hours per (normal) day."""
        return sum(window.minutes for window in self.windows) / 60

    def __str__(self) -> str:
        """``HH:MM-HH:MM HH:MM-HH:MM``, or ``none``."""
        return " ".join(str(window) for window in self.windows) or "none"


NO_OFF_PEAK = OffPeakHours()


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
    cumulative = np.interp(edges, points, inside)
    return np.diff(cumulative)


@dataclass(frozen=True, slots=True)
class TimeClassWeights:
    """The share of each step in each class; every row sums to 1."""

    grid: TimeGrid
    shares: npt.NDArray[np.float64] = field(repr=False)
    """Shape ``(len(grid), 4)``, columns in ``CLASSES`` order."""

    def share(self, time_class: TimeClass) -> TimeSeries:
        """The share of each step in ``time_class`` (dimensionless, 0 to 1)."""
        column = self.shares[:, CLASSES.index(time_class)]
        return TimeSeries(grid=self.grid, values=column.copy(), quantity=Quantity.DIMENSIONLESS)

    def split(self, series: TimeSeries) -> Mapping[TimeClass, float]:
        """Energy (kWh) of a power or energy series in each class; the values add up to its total.

        Raises:
            SeriesError: the series is on another grid, or is neither power nor energy.
        """
        if series.grid != self.grid:
            msg = "the series and the time classes are on different grids"
            raise SeriesError(msg)
        if series.quantity not in {Quantity.POWER_KW, Quantity.ENERGY_KWH}:
            msg = f"only power or energy can be split by time class, not {series.quantity.value}"
            raise SeriesError(msg)
        energy = series.energy() if series.quantity is Quantity.POWER_KW else series
        totals = energy.values @ self.shares
        return {time_class: float(total) for time_class, total in zip(CLASSES, totals, strict=True)}


@dataclass(frozen=True, slots=True)
class TimeClassCalendar:
    """Assigns every instant to a class from a connection's off-peak hours and the seasons."""

    off_peak: OffPeakHours = NO_OFF_PEAK
    high_season_months: frozenset[int] = HIGH_SEASON_MONTHS

    def _days(self, grid: TimeGrid) -> list[date]:
        first = grid.start.astimezone(grid.timezone).date() - timedelta(days=1)
        last = grid.end.astimezone(grid.timezone).date() + timedelta(days=1)
        return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]

    def _off_peak(self, days: list[date], zone: ZoneInfo) -> _Intervals:
        return _union(
            (
                _instant(day, window.start, zone),
                _instant(day + timedelta(days=window.end <= window.start), window.end, zone),
            )
            for day in days
            for window in self.off_peak.windows
        )

    def _high_season(self, days: list[date], zone: ZoneInfo) -> _Intervals:
        return _union(
            (_instant(day, time(), zone), _instant(day + timedelta(days=1), time(), zone))
            for day in days
            if day.month in self.high_season_months
        )

    def weights(self, grid: TimeGrid) -> TimeClassWeights:
        """The share of each step of ``grid`` in each class, on the grid's wall clock."""
        days = self._days(grid)
        off_peak = self._off_peak(days, grid.timezone)
        high = self._high_season(days, grid.timezone)
        edges = grid.start.timestamp() + grid.edges_seconds()
        step = grid.step.total_seconds()
        hch = _seconds_inside(_intersection(off_peak, high), edges) / step
        hph = _seconds_inside(high, edges) / step - hch
        hcb = _seconds_inside(off_peak, edges) / step - hch
        hpb = 1.0 - hph - hch - hcb
        return TimeClassWeights(grid=grid, shares=np.column_stack([hph, hch, hpb, hcb]))
