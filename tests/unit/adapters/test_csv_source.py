"""User CSV profiles: strict format, unit conversion, interval labels."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.profiles.csv_files import (
    HEADER,
    MAX_BYTES,
    MIN_ROWS,
    CsvProfile,
    CsvProfileSource,
    CsvUnit,
    load,
)
from myenergy.domain.profiles import ProfileKind, ProfileUnit, TimestampLabel
from myenergy.domain.time import TimeGrid

H = timedelta(hours=1)


def write(tmp_path: Path, text: str, name: str = "p.csv") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def profile(
    path: Path, unit: CsvUnit = CsvUnit.KW, label: TimestampLabel = TimestampLabel.START
) -> CsvProfile:
    return CsvProfile(key="p", path=path, kind=ProfileKind.CONSUMPTION, unit=unit, label=label)


GOOD = (
    "timestamp,value\n2026-01-01T00:00:00+00:00,1\n"
    "2026-01-01T01:00:00+00:00,2\n2026-01-01T02:00:00+00:00,4\n"
)


def test_constants() -> None:
    assert (HEADER, MIN_ROWS, MAX_BYTES) == (["timestamp", "value"], 2, 20 * 1024 * 1024)


def test_kw_values_are_kept_as_measured_power(tmp_path: Path) -> None:
    meta, shape = load(profile(write(tmp_path, GOOD)))
    assert meta.unit is ProfileUnit.KW
    assert meta.coverage == TimeGrid(
        start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 1, 1, 3, tzinfo=UTC), step=H
    )
    assert shape.values.tolist() == [1, 2, 4]
    assert meta.description == "user-supplied profile"


def test_kwh_per_step_becomes_kw(tmp_path: Path) -> None:
    text = "timestamp,value\n2026-01-01T00:00:00Z,1\n2026-01-01T00:30:00Z,2\n"
    _, shape = load(profile(write(tmp_path, text), CsvUnit.KWH))
    assert shape.values.tolist() == [2, 4]


def test_shapes_stay_shapes(tmp_path: Path) -> None:
    meta, _ = load(profile(write(tmp_path, GOOD), CsvUnit.SHAPE))
    assert meta.unit is ProfileUnit.SHAPE


def test_end_labels_move_back_one_step(tmp_path: Path) -> None:
    meta, _ = load(profile(write(tmp_path, GOOD), label=TimestampLabel.END))
    assert meta.coverage.start == datetime(2025, 12, 31, 23, tzinfo=UTC)
    assert meta.label is TimestampLabel.END


def test_offsets_and_byte_order_mark_are_handled(tmp_path: Path) -> None:
    text = "﻿timestamp, value \n2026-01-01T01:00:00+01:00,1\n2026-01-01T02:00:00+01:00,1\n"
    meta, _ = load(profile(write(tmp_path, text)))
    assert meta.coverage.start == datetime(2026, 1, 1, tzinfo=UTC)


def test_source_wraps_the_files(tmp_path: Path) -> None:
    source = CsvProfileSource([profile(write(tmp_path, GOOD))], name="mine")
    assert source.name == "mine"
    assert [m.key for m in source.catalog()] == ["p"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("time,value\n", "p.csv:1: the header must be exactly 'timestamp,value'"),
        ("", "p.csv:1: the header must be exactly"),
        ("timestamp,value\n2026-01-01T00:00:00Z,1,9\n", "p.csv:2: expected 2 fields, got 3"),
        ("timestamp,value\nyesterday,1\n", "p.csv:2: Invalid isoformat string"),
        (
            "timestamp,value\n2026-01-01T00:00:00Z,one\n",
            "p.csv:2: could not convert string to float",
        ),
        (
            "timestamp,value\n2026-01-01T00:00:00,1\n",
            "p.csv:2: timestamp '2026-01-01T00:00:00' has no UTC offset",
        ),
        (
            "timestamp,value\n2026-01-01T00:00:00Z,nan\n",
            "p.csv:2: value 'nan' is not a finite number",
        ),
        (
            "timestamp,value\n2026-01-01T01:00:00Z,1\n2026-01-01T00:00:00Z,1\n",
            "p.csv:3: timestamps must strictly increase",
        ),
        ("timestamp,value\n2026-01-01T00:00:00Z,1\n", "p.csv: at least 2 rows are needed"),
        (
            "timestamp,value\n2026-01-01T00:00:00Z,1\n2026-01-01T01:00:00Z,1\n2026-01-01T03:00:00Z,1\n",
            "p.csv:4: irregular step 2:00:00 \\(expected 1:00:00\\)",
        ),
        (
            "timestamp,value\n2026-01-01T00:07:00Z,1\n2026-01-01T00:22:00Z,1\n",
            "p.csv: start .* is not aligned",
        ),
        (
            "timestamp,value\n2026-01-01T00:00:00Z,1\n2026-01-01T00:07:00Z,1\n",
            "p.csv: step 0:07:00 is not supported",
        ),
    ],
)
def test_format_errors_say_where(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(DataFormatError, match=message):
        load(profile(write(tmp_path, text)))
