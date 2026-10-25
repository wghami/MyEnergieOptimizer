"""Untrusted CSV input is bounded and cannot crash the reader with raw exceptions (SEC-1, SEC-5)."""

from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.profiles.csv_files import CsvProfile, CsvUnit, load
from myenergy.domain.profiles import ProfileKind


def profile(path: Path) -> CsvProfile:
    return CsvProfile(key="p", path=path, kind=ProfileKind.CONSUMPTION, unit=CsvUnit.KW)


def test_oversized_files_are_refused_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "big.csv"
    path.write_text("x" * 101)
    with pytest.raises(DataFormatError, match=r"big\.csv: 101 bytes; the limit is 100"):
        load(profile(path), max_bytes=100)


def test_binary_input_is_a_format_error(tmp_path: Path) -> None:
    path = tmp_path / "bin.csv"
    path.write_bytes(b"timestamp,value\n\xff\xfe\x00\x81garbage\n")
    with pytest.raises(
        DataFormatError, match=r"bin\.csv: not a UTF-8 CSV file \(UnicodeDecodeError\)"
    ):
        load(profile(path))


def test_huge_fields_are_a_format_error(tmp_path: Path) -> None:
    path = tmp_path / "field.csv"
    path.write_text('timestamp,value\n"' + "9" * 200_000 + '",1\n')
    with pytest.raises(DataFormatError, match=r"field\.csv: not a UTF-8 CSV file \(Error\)"):
        load(profile(path))


@pytest.mark.parametrize("value", ["=1+1", "+cmd|' /C calc'!A0", "@SUM(1)"])
def test_formula_like_values_are_rejected_as_numbers(tmp_path: Path, value: str) -> None:
    path = tmp_path / "f.csv"
    path.write_text(f"timestamp,value\n2026-01-01T00:00:00Z,{value}\n")
    with pytest.raises(DataFormatError, match="could not convert"):
        load(profile(path))
