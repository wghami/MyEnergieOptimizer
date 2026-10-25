"""Enedis "coefficients de profils" stored as parquet files (one per sub-profile).

Files are named ``<Category>_<SUBPROFILE>.parquet`` with a UTC ``timestamp`` column labelled by
interval start (SPEC decision 10) and coefficient columns, by default ``coefficient_ajuste``
(decision 11). The resolution changed from 30 to 15 minutes on 2024-10-04 22:00 UTC: each value is
held over its own interval, on the finest native step. Gaps, duplicates and missing values are
errors, never filled (decision 9).
"""

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pyarrow.parquet as pq

from myenergy.adapters.errors import AdapterError, DataFormatError
from myenergy.adapters.profiles.memory import InMemoryProfileSource
from myenergy.domain.profiles import ProfileKind, ProfileMeta, TimestampLabel
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid

_FILE = re.compile(r"(?P<category>[A-Za-zÀ-ÿ]+)_(?P<key>[A-Za-z0-9_-]+)\.parquet")
NATIVE_STEPS = (timedelta(minutes=15), timedelta(minutes=30))
_PRODUCER = "Producteur"


def _seconds(values: npt.NDArray[np.datetime64]) -> npt.NDArray[np.int64]:
    return values.astype("datetime64[s]").astype(np.int64)


class EnedisParquetSource:
    """A ``ProfileSource`` over a folder of Enedis parquet files.

    Raises:
        AdapterError: the folder does not exist.
    """

    def __init__(
        self, root: Path, *, column: str = "coefficient_ajuste", name: str = "enedis"
    ) -> None:
        """Index the files of ``root``; data is read on first use."""
        if not root.is_dir():
            msg = f"Enedis data folder {root} does not exist (set ENEDIS_DB_PATH)"
            raise AdapterError(msg)
        self._name = name
        self._column = column
        self._files = {
            match["key"]: (match["category"], path)
            for path in sorted(root.glob("*.parquet"))
            if (match := _FILE.fullmatch(path.name)) is not None
        }
        self._memory: InMemoryProfileSource | None = None

    @property
    def name(self) -> str:
        """The source name used in ``ProfileRef.source``."""
        return self._name

    def _load(self, key: str, category: str, path: Path) -> tuple[ProfileMeta, TimeSeries]:
        table = pq.read_table(path, columns=["timestamp", self._column])  # pyright: ignore[reportUnknownMemberType]  # pyarrow-stubs leave unused parameters untyped
        values_column = table.column(self._column)
        if values_column.null_count:
            msg = f"{path.name}: {values_column.null_count} missing {self._column} values"
            raise DataFormatError(msg)
        raw_stamps = _seconds(table.column("timestamp").to_numpy())
        order = np.argsort(raw_stamps, kind="stable")
        stamps = raw_stamps[order]
        values = np.asarray(values_column.to_numpy(), dtype=np.float64)[order]
        gaps = np.diff(stamps)
        allowed = [int(step.total_seconds()) for step in NATIVE_STEPS]
        bad = np.flatnonzero(~np.isin(gaps, allowed))
        if bad.size:
            at = datetime.fromtimestamp(int(stamps[bad[0]]), tz=UTC).isoformat()
            msg = (
                f"{path.name}: {gaps[bad[0]]} s between {at} and the next row; native steps "
                f"are {', '.join(str(s) for s in NATIVE_STEPS)}"
            )
            raise DataFormatError(msg)
        finest = int(gaps.min()) if gaps.size else allowed[0]
        lengths = np.append(gaps, gaps[-1] if gaps.size else finest)
        start = datetime.fromtimestamp(int(stamps[0]), tz=UTC)
        coverage = TimeGrid(
            start=start,
            end=start + timedelta(seconds=int(lengths.sum())),
            step=timedelta(seconds=finest),
        )
        shape = TimeSeries(
            grid=coverage,
            values=np.repeat(values, lengths // finest),
            quantity=Quantity.DIMENSIONLESS,
        )
        kind = ProfileKind.PRODUCTION if category == _PRODUCER else ProfileKind.CONSUMPTION
        meta = ProfileMeta(
            key=key,
            kind=kind,
            coverage=coverage,
            label=TimestampLabel.START,
            description=f"Enedis {category} {key} ({self._column})",
        )
        return meta, shape

    def _source(self) -> InMemoryProfileSource:
        if self._memory is None:
            loaded = {key: self._load(key, *where) for key, where in self._files.items()}
            self._memory = InMemoryProfileSource(self._name, loaded)
        return self._memory

    def catalog(self) -> Sequence[ProfileMeta]:
        """Every sub-profile found in the folder."""
        return self._source().catalog()

    def shape(self, key: str, grid: TimeGrid) -> TimeSeries:
        """The shape of sub-profile ``key`` on ``grid``."""
        return self._source().shape(key, grid)
