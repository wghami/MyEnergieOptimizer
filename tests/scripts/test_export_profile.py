"""The export script writes kW profiles for every source, and reports errors cleanly (TST-15)."""

import csv
import runpy
from pathlib import Path

import pytest

from scripts.export_profile import main

FIXTURES = Path(__file__).parents[1] / "fixtures"
WINDOW = ["--start", "2024-10-01T00:00+02:00", "--end", "2024-10-02T00:00+02:00"]


def _rows(path: Path) -> list[list[str]]:
    with path.open(newline="") as handle:
        return list(csv.reader(handle))


def test_synthetic_nominal(tmp_path: Path) -> None:
    out = tmp_path / "s.csv"
    assert (
        main(
            [
                "--source",
                "synthetic",
                "--key",
                "household",
                "--annual-kwh",
                "3500",
                *WINDOW,
                "--step",
                "60",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    rows = _rows(out)
    assert rows[0] == ["timestamp", "power_kw"]
    assert len(rows) == 25
    assert rows[1][0] == "2024-09-30T22:00:00+00:00"


def test_enedis_calibrated_and_pv(tmp_path: Path) -> None:
    out = tmp_path / "e.csv"
    calibrate = ["--calibrate", "12", "2024-10-01T00:00+02:00", "2024-10-02T00:00+02:00"]
    common = [
        "--source",
        "enedis",
        "--enedis-root",
        str(FIXTURES / "enedis"),
        *WINDOW,
        "--out",
        str(out),
    ]
    assert main([*common, "--key", "RES1_BASE", *calibrate]) == 0
    energy = sum(float(row[1]) for row in _rows(out)[1:]) * 0.25
    assert energy == pytest.approx(12, rel=1e-5)  # six-decimal rounding of 96 values
    assert main([*common, "--key", "PRD3_BASE", "--pv", "3", "1200"]) == 0


def test_enedis_root_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ENEDIS_DB_PATH", str(FIXTURES / "enedis"))
    assert (
        main(
            [
                "--source",
                "enedis",
                "--key",
                "RES1_BASE",
                "--annual-kwh",
                "1000",
                *WINDOW,
                "--step",
                "60",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.startswith("timestamp,power_kw")
    monkeypatch.delenv("ENEDIS_DB_PATH")
    assert main(["--source", "enedis", "--key", "RES1_BASE", "--annual-kwh", "1", *WINDOW]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_csv_as_measured(tmp_path: Path) -> None:
    out = tmp_path / "c.csv"
    assert (
        main(
            [
                "--source",
                "csv",
                "--csv",
                str(FIXTURES / "csv" / "home-kw.csv"),
                "--as-measured",
                "--start",
                "2026-01-05T00:00+01:00",
                "--end",
                "2026-01-06T00:00+01:00",
                "--step",
                "30",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    assert _rows(out)[1] == ["2026-01-04T23:00:00+00:00", "0.400000"]


def test_errors_are_reported_not_raised(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--source", "synthetic", "--key", "household", "--annual-kwh", "-1", *WINDOW]) == 2
    assert capsys.readouterr().err == "error: annual_kwh must be positive, got -1.0\n"


def test_runs_as_a_program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "p.csv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_profile",
            "--source",
            "synthetic",
            "--key",
            "constant",
            "--annual-kwh",
            "8760",
            *WINDOW,
            "--out",
            str(out),
        ],
    )
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(
            str(Path(__file__).parents[2] / "scripts" / "export_profile.py"), run_name="__main__"
        )
    assert exit_info.value.code == 0
    assert _rows(out)[1][1] == "1.000000"
