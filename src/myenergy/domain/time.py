"""Time grids: the half-open UTC ranges, split into equal steps, that every series lives on.

A grid is held in UTC, so daylight-saving changes cannot break it: a local day simply has 23 or 25
hours. The grid's ``timezone`` is only used for wall-clock logic (seasons, peak hours). Steps divide
an hour (SPEC decision 8), and the start is aligned on the step, so grids of the same step line up.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Self
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt

from myenergy.domain.errors import GridError

ALLOWED_STEPS = tuple(timedelta(minutes=m) for m in (5, 10, 15, 20, 30, 60))
DEFAULT_TIMEZONE = ZoneInfo("Europe/Paris")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _utc(moment: datetime, name: str) -> datetime:
    if moment.tzinfo is None or moment.utcoffset() is None:
        msg = f"{name} must be timezone-aware, got {moment.isoformat()}"
        raise GridError(msg)
    return moment.astimezone(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeGrid:
    """``[start, end)`` in UTC, divided into ``step``-long intervals labelled by their start.

    Raises:
        GridError: naive or misaligned timestamps, an unsupported step, or an empty range.
    """

    start: datetime
    end: datetime
    step: timedelta
    timezone: ZoneInfo = field(default=DEFAULT_TIMEZONE)

    def __post_init__(self) -> None:
        """Normalise to UTC and check the grid rules."""
        start, end = _utc(self.start, "start"), _utc(self.end, "end")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if self.step not in ALLOWED_STEPS:
            allowed = ", ".join(f"{int(s.total_seconds() // 60)}" for s in ALLOWED_STEPS)
            msg = f"step {self.step} is not supported; use one of {allowed} minutes"
            raise GridError(msg)
        if end <= start:
            msg = f"the grid is empty: end {end.isoformat()} is not after start {start.isoformat()}"
            raise GridError(msg)
        if (start - _EPOCH) % self.step:
            msg = f"start {start.isoformat()} is not aligned on the {self.step} step"
            raise GridError(msg)
        if (end - start) % self.step:
            msg = f"the span {end - start} is not a whole number of {self.step} steps"
            raise GridError(msg)

    @classmethod
    def covering(cls, start: datetime, end: datetime, step: timedelta) -> Self:
        """The grid from ``start`` to ``end`` in the default timezone (convenience)."""
        return cls(start=start, end=end, step=step)

    def __len__(self) -> int:
        """Number of steps."""
        return (self.end - self.start) // self.step

    def __iter__(self) -> Iterator[datetime]:
        """Every step's start, in UTC."""
        return (self.start + i * self.step for i in range(len(self)))

    @property
    def step_hours(self) -> float:
        """The step length in hours (to turn kW into kWh)."""
        return self.step / timedelta(hours=1)

    @property
    def span(self) -> timedelta:
        """``end - start``."""
        return self.end - self.start

    def timestamp(self, index: int) -> datetime:
        """Start of step ``index`` (negative indices count from the end), in UTC.

        Raises:
            GridError: the index is outside the grid.
        """
        size = len(self)
        if not -size <= index < size:
            msg = f"step {index} is outside a grid of {size} steps"
            raise GridError(msg)
        return self.start + (index % size) * self.step

    def local(self, index: int) -> datetime:
        """Start of step ``index`` on the grid's wall clock."""
        return self.timestamp(index).astimezone(self.timezone)

    def index(self, moment: datetime) -> int:
        """The step that starts at ``moment``.

        Raises:
            GridError: ``moment`` is naive, outside the grid, or not a step boundary.
        """
        moment = _utc(moment, "moment")
        if not self.start <= moment < self.end:
            bounds = f"[{self.start.isoformat()}, {self.end.isoformat()})"
            msg = f"{moment.isoformat()} is outside {bounds}"
            raise GridError(msg)
        offset = moment - self.start
        if offset % self.step:
            msg = f"{moment.isoformat()} is not a step boundary of this grid"
            raise GridError(msg)
        return offset // self.step

    def edges_seconds(self) -> npt.NDArray[np.float64]:
        """The ``len + 1`` step edges, in seconds since ``start`` (for resampling)."""
        return np.arange(len(self) + 1, dtype=np.float64) * self.step.total_seconds()

    def contains(self, other: "TimeGrid") -> bool:
        """True when ``other``'s range lies within this grid's range (any step)."""
        return self.start <= other.start and other.end <= self.end

    def sub(self, start: datetime, end: datetime) -> "TimeGrid":
        """The part of this grid from ``start`` to ``end``, same step and timezone.

        Raises:
            GridError: the range is outside this grid or not aligned on its steps.
        """
        part = TimeGrid(start=start, end=end, step=self.step, timezone=self.timezone)
        if not self.contains(part):
            msg = f"[{part.start.isoformat()}, {part.end.isoformat()}) is outside this grid"
            raise GridError(msg)
        return part

    def with_step(self, step: timedelta) -> "TimeGrid":
        """The same range with another step.

        Raises:
            GridError: the range is not a whole number of the new steps.
        """
        return TimeGrid(start=self.start, end=self.end, step=step, timezone=self.timezone)
