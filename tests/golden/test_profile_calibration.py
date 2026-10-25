"""Golden cases for M1: calibration on real Enedis data is exact over its window, at any step.

The committed fixture runs everywhere. The full-year case runs only where the full Enedis database
is configured (``ENEDIS_DB_PATH``), as personal or large data never enters the repository (SEC-14).
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from myenergy.adapters.profiles.enedis import EnedisParquetSource
from myenergy.domain.profiles import Calibrated, Nominal, ProfileRef, Shaped
from myenergy.domain.time import TimeGrid
from myenergy.engine.profiles import ProfileResolver

PARIS = ZoneInfo("Europe/Paris")
FIXTURES = Path(__file__).parents[1] / "fixtures" / "enedis"
RES1 = ProfileRef(source="enedis", key="RES1_BASE")


def _resolver(root: Path) -> ProfileResolver:
    return ProfileResolver({"enedis": EnedisParquetSource(root)})


@pytest.mark.parametrize("minutes", [5, 15, 20, 30, 60])
def test_fortnight_calibration_is_exact_at_any_step(minutes: int) -> None:
    window = TimeGrid(
        start=datetime(2024, 9, 29, tzinfo=PARIS),
        end=datetime(2024, 10, 13, tzinfo=PARIS),
        step=timedelta(minutes=minutes),
    )
    spec = Shaped(ref=RES1, scaling=Calibrated(energy_kwh=150.0, window=window))
    assert _resolver(FIXTURES).power(spec, window).energy().total() == pytest.approx(
        150.0, rel=1e-12
    )


@pytest.mark.skipif("ENEDIS_DB_PATH" not in os.environ, reason="needs the full Enedis database")
def test_billing_year_from_october_on_the_full_database() -> None:
    root = Path(os.environ["ENEDIS_DB_PATH"])
    year = TimeGrid(
        start=datetime(2024, 10, 1, tzinfo=PARIS),
        end=datetime(2025, 10, 1, tzinfo=PARIS),
        step=timedelta(minutes=15),
    )
    resolver = _resolver(root)
    calibrated = resolver.power(
        Shaped(ref=RES1, scaling=Calibrated(energy_kwh=3500.0, window=year)), year
    )
    assert calibrated.energy().total() == pytest.approx(3500.0, rel=1e-9)
    nominal = resolver.power(Shaped(ref=RES1, scaling=Nominal(annual_kwh=3500.0)), year)
    assert nominal.energy().total() == pytest.approx(
        3500.0, rel=0.01
    )  # the data's own year: close, not equal
