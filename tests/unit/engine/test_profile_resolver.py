"""Profile specs become kW series, from any registered source (SPEC §6)."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from myenergy.adapters.profiles.memory import InMemoryProfileSource
from myenergy.domain.errors import CalibrationError, GridError, UnknownProfileError
from myenergy.domain.profiles import (
    Calibrated,
    Nominal,
    ProfileKind,
    ProfileMeta,
    ProfileRef,
    PVSystem,
    Shaped,
    TimestampLabel,
)
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid
from myenergy.engine.profiles import ProfileResolver

START = datetime(2026, 1, 5, tzinfo=UTC)
H = timedelta(hours=1)
NATIVE = TimeGrid(start=START, end=START + 48 * H, step=H)
SHAPE = np.tile(np.concatenate([np.full(12, 0.5), np.full(12, 1.5)]), 2)  # mean 1, two days


def resolver(values: np.ndarray = SHAPE) -> ProfileResolver:
    meta = ProfileMeta(
        key="home",
        kind=ProfileKind.CONSUMPTION,
        coverage=NATIVE,
        label=TimestampLabel.START,
        description="test",
    )
    series = TimeSeries(grid=NATIVE, values=values, quantity=Quantity.DIMENSIONLESS)
    return ProfileResolver({"mem": InMemoryProfileSource("mem", {"home": (meta, series)})})


REF = ProfileRef(source="mem", key="home")


def test_nominal_scaling() -> None:
    power = resolver().power(Shaped(ref=REF, scaling=Nominal(annual_kwh=8760)), NATIVE)
    assert power.quantity is Quantity.POWER_KW
    assert power.values.tolist() == SHAPE.tolist()


def test_pv_system_scaling() -> None:
    spec = Shaped(ref=REF, scaling=PVSystem(peak_kwp=2, specific_yield_kwh_per_kwp=4380))
    assert resolver().power(spec, NATIVE).values[0] == pytest.approx(0.5)


def test_calibration_is_exact_over_its_window_for_any_step() -> None:
    first_morning = NATIVE.sub(START, START + 12 * H)  # shape 0.5 there
    spec = Shaped(ref=REF, scaling=Calibrated(energy_kwh=3.0, window=first_morning))
    for step in (timedelta(minutes=5), timedelta(minutes=20), H):
        energy = resolver().power(spec, first_morning.with_step(step)).energy()
        assert energy.total() == pytest.approx(3.0, rel=1e-12)
    whole = resolver().power(spec, NATIVE).energy().total()
    assert whole == pytest.approx(24.0)  # per day: morning 3 kWh + afternoon (3x the shape) 9 kWh


def test_calibrating_on_a_window_without_energy_is_refused() -> None:
    spec = Shaped(ref=REF, scaling=Calibrated(energy_kwh=1.0, window=NATIVE))
    with pytest.raises(CalibrationError, match="the shape integrates to 0"):
        resolver(np.zeros(48)).power(spec, NATIVE)


def test_time_shift_moves_the_curve_later() -> None:
    later = ProfileRef(source="mem", key="home", time_shift=timedelta(hours=12))
    grid = NATIVE.sub(START + 12 * H, START + 36 * H)
    shifted = resolver().shape(later, grid)
    assert shifted.grid == grid
    assert (
        shifted.values.tolist()
        == resolver().shape(REF, NATIVE.sub(START, START + 24 * H)).values.tolist()
    )
    with pytest.raises(GridError, match="not aligned"):
        resolver().shape(
            ProfileRef(source="mem", key="home", time_shift=timedelta(minutes=10)), grid
        )


def test_unknown_sources_name_the_registered_ones() -> None:
    with pytest.raises(
        UnknownProfileError, match=r"no profile source 'enedis' \(registered: mem\)"
    ):
        resolver().shape(ProfileRef(source="enedis", key="x"), NATIVE)
    with pytest.raises(UnknownProfileError, match=r"\(registered: none\)"):
        ProfileResolver({}).shape(REF, NATIVE)


def test_sources_are_registered_under_their_own_name() -> None:
    source = InMemoryProfileSource("mem", {})
    with pytest.raises(
        UnknownProfileError, match="source registered as 'other' calls itself 'mem'"
    ):
        ProfileResolver({"other": source})
