"""Profile references, metadata and scalings (SPEC §6, decisions 7, 10, 12)."""

from datetime import UTC, datetime, timedelta

import pytest

from myenergy.domain.errors import CalibrationError, UnknownProfileError
from myenergy.domain.profiles import (
    HOURS_PER_NOMINAL_YEAR,
    Calibrated,
    Nominal,
    ProfileKind,
    ProfileRef,
    PVSystem,
    TimestampLabel,
)
from myenergy.domain.time import TimeGrid

DAY = TimeGrid(
    start=datetime(2026, 1, 1, tzinfo=UTC),
    end=datetime(2026, 1, 2, tzinfo=UTC),
    step=timedelta(hours=1),
)


def test_enumerations() -> None:
    assert [k.value for k in ProfileKind] == ["consumption", "production"]
    assert [label.value for label in TimestampLabel] == ["start", "end"]


def test_references_default_to_no_shift() -> None:
    ref = ProfileRef(source="enedis", key="RES1_BASE")
    assert ref.time_shift == timedelta(0)


@pytest.mark.parametrize(("source", "key"), [("", "RES1_BASE"), ("enedis", "")])
def test_references_need_a_source_and_a_key(source: str, key: str) -> None:
    with pytest.raises(UnknownProfileError, match="needs a source and a key"):
        ProfileRef(source=source, key=key)


def test_nominal_is_annual_energy_per_8760_hours() -> None:
    assert HOURS_PER_NOMINAL_YEAR == 8760.0
    assert Nominal(annual_kwh=3504).kw_per_unit() == pytest.approx(0.4)


def test_pv_system_is_a_nominal_energy() -> None:
    assert PVSystem(peak_kwp=3, specific_yield_kwh_per_kwp=1200).nominal() == Nominal(
        annual_kwh=3600
    )


def test_calibration_divides_by_the_shape_energy() -> None:
    assert Calibrated(energy_kwh=10, window=DAY).kw_per_unit(shape_unit_hours=25) == 0.4
    with pytest.raises(
        CalibrationError,
        match=r"cannot calibrate on \[2026-01-01T00:00:00\+00:00, "
        r"2026-01-02T00:00:00\+00:00\): the shape integrates to 0",
    ):
        Calibrated(energy_kwh=10, window=DAY).kw_per_unit(shape_unit_hours=0)


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (lambda: Nominal(annual_kwh=0), "annual_kwh must be positive, got 0"),
        (lambda: Calibrated(energy_kwh=-1, window=DAY), "energy_kwh must be positive, got -1"),
        (
            lambda: PVSystem(peak_kwp=0, specific_yield_kwh_per_kwp=1000),
            "peak_kwp must be positive",
        ),
        (
            lambda: PVSystem(peak_kwp=3, specific_yield_kwh_per_kwp=0),
            "specific_yield_kwh_per_kwp must",
        ),
    ],
)
def test_scalings_need_positive_values(build: object, message: str) -> None:
    with pytest.raises(CalibrationError, match=message):
        build()  # pyright: ignore[reportCallIssue]  # each case is a zero-argument lambda


def test_exact_messages() -> None:
    with pytest.raises(UnknownProfileError) as error:
        ProfileRef(source="", key="RES1_BASE")
    assert str(error.value) == "a profile reference needs a source and a key, got ''/'RES1_BASE'"
    with pytest.raises(CalibrationError) as error:
        Calibrated(energy_kwh=0, window=DAY)
    assert str(error.value) == "energy_kwh must be positive, got 0"
    for build, name in (
        (lambda: PVSystem(peak_kwp=0, specific_yield_kwh_per_kwp=1), "peak_kwp"),
        (lambda: PVSystem(peak_kwp=1, specific_yield_kwh_per_kwp=0), "specific_yield_kwh_per_kwp"),
    ):
        with pytest.raises(CalibrationError) as error:
            build()
        assert str(error.value) == f"{name} must be positive, got 0"


def test_calibration_accepts_small_positive_energies() -> None:
    assert Calibrated(energy_kwh=1, window=DAY).kw_per_unit(shape_unit_hours=0.5) == 2.0
