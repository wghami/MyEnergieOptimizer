"""Time series: quantity-tagged values that combine and resample correctly (SPEC §3)."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from myenergy.domain.errors import CoverageError, SeriesError
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid

H = timedelta(hours=1)
Q = timedelta(minutes=15)


def grid(start_hour: int = 0, hours: int = 4, step: timedelta = H) -> TimeGrid:
    start = datetime(2026, 1, 1, start_hour, tzinfo=UTC)
    return TimeGrid(start=start, end=start + hours * H, step=step)


def power(values: list[float], step: timedelta = H) -> TimeSeries:
    hours = int(len(values) * step / H)
    return TimeSeries(
        grid=grid(hours=hours, step=step), values=np.array(values), quantity=Quantity.POWER_KW
    )


def test_quantities() -> None:
    assert [q.value for q in Quantity] == ["kW", "kWh", "EUR/kWh", "1"]
    assert [q.extensive for q in Quantity] == [False, True, False, False]


def test_values_are_a_read_only_copy() -> None:
    source = np.array([1.0, 2.0, 3.0, 4.0])
    series = TimeSeries(grid=grid(), values=source, quantity=Quantity.POWER_KW)
    source[0] = 99.0
    assert series.values[0] == 1.0
    with pytest.raises(ValueError, match="read-only"):
        series.values[0] = 5.0
    assert series.values.dtype == np.float64
    assert len(series) == 4


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ([1.0, 2.0], r"\(2,\) values do not match a grid of 4 steps"),
        ([1.0, float("nan"), 1.0, 1.0], "only finite numbers"),
        ([1.0, float("inf"), 1.0, 1.0], "only finite numbers"),
    ],
)
def test_invalid_values_are_refused(values: list[float], message: str) -> None:
    with pytest.raises(SeriesError, match=message):
        TimeSeries(grid=grid(), values=np.array(values), quantity=Quantity.POWER_KW)


def test_constant() -> None:
    series = TimeSeries.constant(grid(), 2.5, Quantity.PRICE_EUR_PER_KWH)
    assert series.values.tolist() == [2.5] * 4
    assert series.quantity is Quantity.PRICE_EUR_PER_KWH


def test_arithmetic_needs_the_same_grid_and_quantity() -> None:
    a = power([1, 2, 3, 4])
    b = power([1, 1, 1, 1])
    assert (a + b).values.tolist() == [2, 3, 4, 5]
    assert (a - b).values.tolist() == [0, 1, 2, 3]
    assert (a - b).quantity is Quantity.POWER_KW
    with pytest.raises(SeriesError, match="cannot add kWh to kW"):
        _ = a + a.energy()
    with pytest.raises(SeriesError, match="cannot add series on different grids"):
        _ = a + power([1] * 8, step=timedelta(minutes=30))


def test_scaling_and_retagging() -> None:
    shape = TimeSeries(
        grid=grid(), values=np.array([0.5, 1, 1.5, 1]), quantity=Quantity.DIMENSIONLESS
    )
    load = shape.scaled(2.0, Quantity.POWER_KW)
    assert (load.values.tolist(), load.quantity) == ([1, 2, 3, 2], Quantity.POWER_KW)
    assert shape.scaled(3.0).quantity is Quantity.DIMENSIONLESS


def test_power_and_energy_round_trip() -> None:
    quarter = power([4.0, 8.0], step=Q * 2)  # 30-minute steps
    energy = quarter.energy()
    assert (energy.values.tolist(), energy.quantity) == ([2.0, 4.0], Quantity.ENERGY_KWH)
    assert energy.total() == 6.0
    assert energy.power().isclose(quarter)
    with pytest.raises(SeriesError, match="energy\\(\\) needs a kW series, not kWh"):
        energy.energy()
    with pytest.raises(SeriesError, match="power\\(\\) needs a kWh series, not kW"):
        quarter.power()


def test_totals_and_means_by_kind() -> None:
    load = power([1, 2, 3, 6])
    assert load.time_mean() == 3.0
    with pytest.raises(SeriesError, match="total\\(\\) is for energy; use time_mean\\(\\) for kW"):
        load.total()
    with pytest.raises(SeriesError, match="time_mean\\(\\) is for rates and shapes"):
        load.energy().time_mean()


def test_downsampling_averages_power_and_sums_energy() -> None:
    quarter = TimeSeries(
        grid=grid(step=Q), values=np.arange(16, dtype=float), quantity=Quantity.POWER_KW
    )
    hourly = quarter.resample(grid())
    assert hourly.values.tolist() == [1.5, 5.5, 9.5, 13.5]
    assert quarter.energy().resample(grid()).values.tolist() == pytest.approx([1.5, 5.5, 9.5, 13.5])


def test_upsampling_holds_power_and_splits_energy() -> None:
    hourly = power([4, 8, 0, 2])
    quarter = hourly.resample(grid(step=Q))
    assert quarter.values.tolist()[:5] == [4, 4, 4, 4, 8]
    assert hourly.energy().resample(grid(step=Q)).values.tolist()[:5] == [1, 1, 1, 1, 2]


def test_non_integer_ratio_uses_overlaps() -> None:
    twenty = TimeSeries(
        grid=grid(hours=1, step=timedelta(minutes=20)),
        values=np.array([3.0, 6.0, 9.0]),
        quantity=Quantity.POWER_KW,
    )
    quarter = twenty.resample(grid(hours=1, step=Q))
    assert quarter.values.tolist() == pytest.approx([3.0, 5.0, 7.0, 9.0])  # (5*3 + 10*6) / 15 = 5


def test_resampling_a_sub_period() -> None:
    hourly = power([1, 2, 3, 4])
    middle = hourly.resample(grid(start_hour=1, hours=2, step=timedelta(minutes=30)))
    assert middle.values.tolist() == [2, 2, 3, 3]


def test_resampling_outside_the_data_is_an_error() -> None:
    with pytest.raises(CoverageError, match=r"cannot resample to \[2026-01-01T03:00:00\+00:00, "):
        power([1, 2, 3, 4]).resample(grid(start_hour=3, hours=2))


def test_isclose() -> None:
    a = power([1, 2, 3, 4])
    assert a.isclose(power([1, 2, 3, 4 + 1e-15]))
    assert not a.isclose(power([1, 2, 3, 4.1]))
    assert not a.isclose(a.energy())
    assert not a.isclose(power([1] * 8, step=timedelta(minutes=30)))
