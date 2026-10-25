"""Synthetic shapes are deterministic, normalised, and independent of the requested window."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from myenergy.adapters.profiles.synthetic import (
    COVERAGE,
    REFERENCE_YEAR,
    STEPS_PER_DAY,
    SyntheticProfileSource,
)
from myenergy.domain.errors import CoverageError, UnknownProfileError
from myenergy.domain.time import TimeGrid

Q = timedelta(minutes=15)


def grid(start: datetime, days: int, step: timedelta = Q) -> TimeGrid:
    return TimeGrid(start=start, end=start + timedelta(days=days), step=step)


def test_constants() -> None:
    assert STEPS_PER_DAY == 288
    assert (COVERAGE.start.year, COVERAGE.end.year, REFERENCE_YEAR.start.year) == (2000, 2100, 2021)


@pytest.mark.parametrize("key", ["household", "pv-clear-sky", "constant"])
def test_mean_is_one_over_the_reference_year(key: str) -> None:
    shape = SyntheticProfileSource().shape(key, REFERENCE_YEAR.with_step(timedelta(hours=1)))
    assert shape.time_mean() == pytest.approx(1.0, rel=0.02 if key == "household" else 1e-9)


def test_values_do_not_depend_on_the_window() -> None:
    source = SyntheticProfileSource(seed=7)
    week = source.shape("household", grid(datetime(2026, 3, 2, tzinfo=UTC), 7))
    day = source.shape("household", grid(datetime(2026, 3, 4, 6, tzinfo=UTC), 1))
    assert np.allclose(week.resample(day.grid).values, day.values, rtol=1e-12)


def test_seed_changes_only_the_noise() -> None:
    window = grid(datetime(2026, 3, 2, tzinfo=UTC), 1)
    a = SyntheticProfileSource(seed=1).shape("household", window).values
    b = SyntheticProfileSource(seed=2).shape("household", window).values
    assert not np.allclose(a, b)
    assert np.allclose(
        SyntheticProfileSource(seed=1).shape("pv-clear-sky", window).values,
        SyntheticProfileSource(seed=2).shape("pv-clear-sky", window).values,
    )


def test_pv_is_zero_at_night_and_peaks_near_noon() -> None:
    june = SyntheticProfileSource().shape(
        "pv-clear-sky", grid(datetime(2026, 6, 21, tzinfo=UTC), 1, timedelta(hours=1))
    )
    assert june.values[0] == 0.0
    assert int(np.argmax(june.values)) in (11, 12)  # UTC, Paris longitude


def test_location_matters() -> None:
    window = grid(datetime(2026, 12, 21, tzinfo=UTC), 1, timedelta(hours=1))
    north = SyntheticProfileSource(latitude=60.0).shape("pv-clear-sky", window).values.max()
    south = SyntheticProfileSource(latitude=35.0).shape("pv-clear-sky", window).values.max()
    assert south > north


def test_errors() -> None:
    source = SyntheticProfileSource()
    assert source.name == "synthetic"
    with pytest.raises(
        UnknownProfileError,
        match="has no profile 'heat-pump' \\(household, pv-clear-sky, constant\\)",
    ):
        source.shape("heat-pump", grid(datetime(2026, 1, 1, tzinfo=UTC), 1))
    with pytest.raises(CoverageError, match="synthetic profiles cover 2000-2100, not 2099-12-31"):
        source.shape("constant", grid(datetime(2099, 12, 31, tzinfo=UTC), 2))
