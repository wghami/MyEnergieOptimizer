"""The Enedis parquet source: real slices around the 30 → 15-minute switch, and broken files."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from myenergy.adapters.errors import AdapterError, DataFormatError
from myenergy.adapters.profiles.enedis import NATIVE_STEPS, EnedisParquetSource
from myenergy.domain.errors import UnknownProfileError
from myenergy.domain.profiles import ProfileKind, ProfileUnit, TimestampLabel
from myenergy.domain.time import TimeGrid

FIXTURES = Path(__file__).parents[2] / "fixtures" / "enedis"
SWITCH = datetime(2024, 10, 4, 22, tzinfo=UTC)
Q = timedelta(minutes=15)


def test_catalog_from_the_fixture_slices() -> None:
    catalog = {meta.key: meta for meta in EnedisParquetSource(FIXTURES).catalog()}
    assert sorted(catalog) == ["PRD3_BASE", "RES1_BASE"]
    res1, prd3 = catalog["RES1_BASE"], catalog["PRD3_BASE"]
    assert (res1.kind, prd3.kind) == (ProfileKind.CONSUMPTION, ProfileKind.PRODUCTION)
    assert res1.label is TimestampLabel.START
    assert res1.unit is ProfileUnit.SHAPE
    assert res1.description == "Enedis Residentiel RES1_BASE (coefficient_ajuste)"
    assert res1.coverage == TimeGrid(
        start=datetime(2024, 9, 28, 22, tzinfo=UTC),
        end=datetime(2024, 10, 12, 22, tzinfo=UTC),
        step=Q,
    )
    assert NATIVE_STEPS == (Q, 2 * Q)


def test_thirty_minute_values_are_held_over_their_interval() -> None:
    source = EnedisParquetSource(FIXTURES)
    before = TimeGrid(start=SWITCH - timedelta(hours=1), end=SWITCH, step=Q)
    values = source.shape("RES1_BASE", before).values
    assert values[0] == values[1]
    assert values[2] == values[3]
    after = source.shape(
        "RES1_BASE", TimeGrid(start=SWITCH, end=SWITCH + timedelta(hours=1), step=Q)
    )
    assert len(set(after.values.tolist())) > 1  # genuine 15-minute data after the switch


def test_pv_is_dark_at_night() -> None:
    night = TimeGrid(
        start=datetime(2024, 10, 1, 0, tzinfo=UTC), end=datetime(2024, 10, 1, 3, tzinfo=UTC), step=Q
    )
    assert EnedisParquetSource(FIXTURES).shape("PRD3_BASE", night).values.max() < 0.01


def _write(
    folder: Path, name: str, stamps: list[datetime], values: list[float | None] | list[int]
) -> None:
    folder.mkdir(exist_ok=True)
    table = pa.table(  # pyright: ignore[reportUnknownMemberType]  # pyarrow-stubs leave mapping values untyped
        {
            "timestamp": pa.array(stamps, type=pa.timestamp("us", tz="UTC")),
            "coefficient_ajuste": values,
        }
    )
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]  # pyarrow-stubs leave unused parameters untyped
        table, folder / name
    )


START = datetime(2024, 1, 1, tzinfo=UTC)


def test_rows_are_sorted_and_integers_accepted(tmp_path: Path) -> None:
    stamps = [START + Q, START, START + 2 * Q]
    _write(tmp_path / "d", "Producteur_PRD4_BASE.parquet", stamps, [2, 1, 3])
    source = EnedisParquetSource(tmp_path / "d", name="mine")
    assert source.name == "mine"
    shape = source.shape("PRD4_BASE", TimeGrid(start=START, end=START + 3 * Q, step=Q))
    assert shape.values.tolist() == [1.0, 2.0, 3.0]


def test_a_single_row_covers_one_finest_step(tmp_path: Path) -> None:
    _write(tmp_path / "d", "Residentiel_ONE.parquet", [START], [1.5])
    assert EnedisParquetSource(tmp_path / "d").catalog()[0].coverage.end == START + Q


def test_unrecognised_file_names_are_ignored(tmp_path: Path) -> None:
    _write(tmp_path / "d", "notes.parquet", [START, START + Q], [1.0, 1.0])
    assert EnedisParquetSource(tmp_path / "d").catalog() == ()


def test_another_column_can_be_read(tmp_path: Path) -> None:
    folder = tmp_path / "d"
    folder.mkdir()
    table = pa.table(  # pyright: ignore[reportUnknownMemberType]  # pyarrow-stubs leave mapping values untyped
        {
            "timestamp": pa.array([START, START + Q], type=pa.timestamp("us", tz="UTC")),
            "coefficient_prepare": [0.5, 0.7],
        }
    )
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]  # pyarrow-stubs leave unused parameters untyped
        table, folder / "Residentiel_RES1_BASE.parquet"
    )
    source = EnedisParquetSource(folder, column="coefficient_prepare")
    assert source.shape("RES1_BASE", source.catalog()[0].coverage).values.tolist() == [0.5, 0.7]


def test_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(AdapterError, match="does not exist \\(set ENEDIS_DB_PATH\\)"):
        EnedisParquetSource(tmp_path / "absent")


def test_missing_values_are_refused(tmp_path: Path) -> None:
    _write(tmp_path / "d", "Residentiel_X.parquet", [START, START + Q], [1.0, None])
    with pytest.raises(
        DataFormatError, match=r"Residentiel_X\.parquet: 1 missing coefficient_ajuste values"
    ):
        EnedisParquetSource(tmp_path / "d").catalog()


def test_gaps_and_duplicates_are_refused(tmp_path: Path) -> None:
    _write(
        tmp_path / "d",
        "Residentiel_GAP.parquet",
        [START, START + Q, START + 5 * Q],
        [1.0, 1.0, 1.0],
    )
    with pytest.raises(
        DataFormatError, match=r"Residentiel_GAP.parquet: 3600 s between 2024-01-01T00:15:00\+00:00"
    ):
        EnedisParquetSource(tmp_path / "d").catalog()
    _write(tmp_path / "e", "Residentiel_DUP.parquet", [START, START], [1.0, 1.0])
    with pytest.raises(DataFormatError, match="0 s between"):
        EnedisParquetSource(tmp_path / "e").catalog()


def test_data_is_read_once(tmp_path: Path) -> None:
    _write(tmp_path / "d", "Residentiel_X.parquet", [START, START + Q], [1.0, 2.0])
    source = EnedisParquetSource(tmp_path / "d")
    first = source.catalog()
    (tmp_path / "d" / "Residentiel_X.parquet").unlink()
    assert source.catalog() == first
    assert np.isfinite(source.shape("X", first[0].coverage).values).all()


def test_a_thirty_minute_only_file_keeps_its_step(tmp_path: Path) -> None:
    _write(
        tmp_path / "d",
        "Residentiel_HALF.parquet",
        [START, START + 2 * Q, START + 4 * Q],
        [1.0, 2.0, 3.0],
    )
    coverage = EnedisParquetSource(tmp_path / "d").catalog()[0].coverage
    assert coverage == TimeGrid(start=START, end=START + 6 * Q, step=2 * Q)


def test_exact_messages_name_the_source(tmp_path: Path) -> None:
    _write(tmp_path / "d", "Residentiel_GAP.parquet", [START, START + 5 * Q], [1.0, 1.0])
    with pytest.raises(DataFormatError) as error:
        EnedisParquetSource(tmp_path / "d").catalog()
    assert str(error.value) == (
        "Residentiel_GAP.parquet: 4500 s between 2024-01-01T00:00:00+00:00 and the next row; "
        "native steps are 0:15:00, 0:30:00"
    )
    source = EnedisParquetSource(FIXTURES, name="mine")
    with pytest.raises(UnknownProfileError) as unknown:
        source.shape("NOPE", source.catalog()[0].coverage)
    assert str(unknown.value) == "source 'mine' has no profile 'NOPE'"
