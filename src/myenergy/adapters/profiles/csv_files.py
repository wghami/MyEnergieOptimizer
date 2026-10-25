"""User-supplied profiles as CSV files: strict, small, and never guessed (SEC-1, SEC-2).

Each file has exactly the header ``timestamp,value``. Timestamps are ISO 8601 **with** a UTC
offset, strictly increasing, one regular step that divides an hour; values are finite numbers in
the declared unit. Anything else is a ``DataFormatError`` naming the file and line.
"""

import csv
import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path

import numpy as np

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.profiles.memory import InMemoryProfileSource
from myenergy.domain.errors import GridError
from myenergy.domain.profiles import ProfileKind, ProfileMeta, ProfileUnit, TimestampLabel
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid

MAX_BYTES = 20 * 1024 * 1024
"""About ten years of 5-minute values; larger inputs are refused (SEC-1)."""
HEADER = ["timestamp", "value"]
MIN_ROWS = 2


class CsvUnit(StrEnum):
    """What the ``value`` column holds."""

    SHAPE = "1"
    KW = "kW"
    KWH = "kWh"


@dataclass(frozen=True, slots=True, kw_only=True)
class CsvProfile:
    """One CSV file and what it means."""

    key: str
    path: Path
    kind: ProfileKind
    unit: CsvUnit
    label: TimestampLabel = TimestampLabel.START
    description: str = "user-supplied profile"


def _parse(row: list[str], where: str) -> tuple[datetime, float]:
    if len(row) != len(HEADER):
        msg = f"{where}: expected 2 fields, got {len(row)}"
        raise DataFormatError(msg)
    try:
        moment, value = datetime.fromisoformat(row[0].strip()), float(row[1])
    except ValueError as error:
        msg = f"{where}: {error}"
        raise DataFormatError(msg) from None
    if moment.utcoffset() is None:
        msg = f"{where}: timestamp {row[0]!r} has no UTC offset"
        raise DataFormatError(msg)
    if not math.isfinite(value):
        msg = f"{where}: value {row[1]!r} is not a finite number"
        raise DataFormatError(msg)
    return moment, value


def _read(path: Path) -> tuple[list[datetime], list[float]]:
    stamps: list[datetime] = []
    values: list[float] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        no_header: list[str] = []
        header = [cell.strip() for cell in next(reader, no_header)]
        if header != HEADER:
            msg = f"{path.name}:1: the header must be exactly 'timestamp,value', got {header}"
            raise DataFormatError(msg)
        for line, row in enumerate(reader, start=2):
            moment, value = _parse(row, f"{path.name}:{line}")
            if stamps and moment <= stamps[-1]:
                msg = f"{path.name}:{line}: timestamps must strictly increase"
                raise DataFormatError(msg)
            stamps.append(moment)
            values.append(value)
    return stamps, values


def _rows(profile: CsvProfile, max_bytes: int) -> tuple[list[datetime], list[float]]:
    path = profile.path
    size = path.stat().st_size
    if size > max_bytes:
        msg = f"{path.name}: {size} bytes; the limit is {max_bytes}"
        raise DataFormatError(msg)
    try:
        stamps, values = _read(path)
    except (UnicodeDecodeError, csv.Error) as error:
        msg = f"{path.name}: not a UTF-8 CSV file ({type(error).__name__})"
        raise DataFormatError(msg) from None
    if len(stamps) < MIN_ROWS:
        msg = f"{path.name}: at least {MIN_ROWS} rows are needed to know the step"
        raise DataFormatError(msg)
    return stamps, values


def load(profile: CsvProfile, max_bytes: int = MAX_BYTES) -> tuple[ProfileMeta, TimeSeries]:
    """Read and check one CSV profile; kWh per step becomes kW.

    Raises:
        DataFormatError: the file breaks the format (the message says where).
    """
    stamps, values = _rows(profile, max_bytes)
    step = stamps[1] - stamps[0]
    for line, (before, after) in enumerate(itertools.pairwise(stamps), start=3):
        if after - before != step:
            msg = f"{profile.path.name}:{line}: irregular step {after - before} (expected {step})"
            raise DataFormatError(msg)
    shift = step if profile.label is TimestampLabel.END else timedelta(0)
    try:
        grid = TimeGrid(start=stamps[0] - shift, end=stamps[-1] - shift + step, step=step)
    except GridError as error:
        msg = f"{profile.path.name}: {error}"
        raise DataFormatError(msg) from None
    array = np.array(values)
    if profile.unit is CsvUnit.KWH:
        array = array / grid.step_hours
    unit = ProfileUnit.SHAPE if profile.unit is CsvUnit.SHAPE else ProfileUnit.KW
    meta = ProfileMeta(
        key=profile.key,
        kind=profile.kind,
        coverage=grid,
        label=profile.label,
        description=profile.description,
        unit=unit,
    )
    return meta, TimeSeries(grid=grid, values=array, quantity=Quantity.DIMENSIONLESS)


class CsvProfileSource:
    """A ``ProfileSource`` over a fixed list of checked CSV files."""

    def __init__(
        self, profiles: Sequence[CsvProfile], *, name: str = "csv", max_bytes: int = MAX_BYTES
    ) -> None:
        """Read and check every file now, so errors surface before any simulation."""
        loaded = {p.key: load(p, max_bytes) for p in profiles}
        self._memory = InMemoryProfileSource(name, loaded)

    @property
    def name(self) -> str:
        """The source name used in ``ProfileRef.source``."""
        return self._memory.name

    def catalog(self) -> Sequence[ProfileMeta]:
        """Every configured profile."""
        return self._memory.catalog()

    def shape(self, key: str, grid: TimeGrid) -> TimeSeries:
        """The profile ``key`` on ``grid`` (kW profiles are tagged dimensionless until scaled)."""
        return self._memory.shape(key, grid)
