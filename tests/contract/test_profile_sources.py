"""Every ``ProfileSource`` honours the same contract (PRT-1), including test-only ones (PRT-2).

Add a source by adding a factory to ``SOURCES``; nothing else changes.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from myenergy.adapters.profiles.csv_files import CsvProfile, CsvProfileSource, CsvUnit
from myenergy.adapters.profiles.enedis import EnedisParquetSource
from myenergy.adapters.profiles.memory import InMemoryProfileSource
from myenergy.adapters.profiles.synthetic import SyntheticProfileSource
from myenergy.domain.errors import CoverageError, UnknownProfileError
from myenergy.domain.profiles import (
    AsMeasured,
    Nominal,
    ProfileKind,
    ProfileMeta,
    ProfileRef,
    ProfileUnit,
    Shaped,
    TimestampLabel,
)
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid
from myenergy.engine.profiles import ProfileResolver
from myenergy.ports.profiles import ProfileSource

START = datetime(2026, 1, 5, tzinfo=UTC)
NATIVE = TimeGrid(start=START, end=START + timedelta(days=2), step=timedelta(minutes=30))


def _native(values: npt.NDArray[np.float64]) -> TimeSeries:
    return TimeSeries(grid=NATIVE, values=np.array(values), quantity=Quantity.DIMENSIONLESS)


def _memory() -> ProfileSource:
    meta = ProfileMeta(
        key="home",
        kind=ProfileKind.CONSUMPTION,
        coverage=NATIVE,
        label=TimestampLabel.START,
        description="a test household",
    )
    hours = np.arange(len(NATIVE)) / 2
    shape = _native(1 + 0.5 * np.sin(2 * np.pi * hours / 24))
    return InMemoryProfileSource("memory", {"home": (meta, shape)})


class FlatSource:
    """A test-only plugin: a constant shape over a fixed coverage, written against the port only."""

    name = "flat"

    def catalog(self) -> Sequence[ProfileMeta]:
        return (
            ProfileMeta(
                key="one",
                kind=ProfileKind.PRODUCTION,
                coverage=NATIVE,
                label=TimestampLabel.START,
                description="always 1",
            ),
        )

    def shape(self, key: str, grid: TimeGrid) -> TimeSeries:
        if key != "one":
            raise UnknownProfileError(key)
        if not NATIVE.contains(grid):
            raise CoverageError(str(grid))
        return TimeSeries.constant(grid, 1.0, Quantity.DIMENSIONLESS)


FIXTURES = Path(__file__).parents[1] / "fixtures"


def _csv() -> ProfileSource:
    home = CsvProfile(key="home", path=FIXTURES / "csv" / "home-kw.csv",
                      kind=ProfileKind.CONSUMPTION, unit=CsvUnit.KW)  # fmt: skip
    return CsvProfileSource([home])


SOURCES: dict[str, Callable[[], ProfileSource]] = {
    "memory": _memory,
    "flat": FlatSource,
    "enedis": lambda: EnedisParquetSource(FIXTURES / "enedis"),
    "csv": _csv,
    "synthetic": SyntheticProfileSource,
}


@pytest.fixture(params=sorted(SOURCES))
def source(request: pytest.FixtureRequest) -> ProfileSource:
    return SOURCES[request.param]()


def test_catalog_keys_are_unique_and_described(source: ProfileSource) -> None:
    catalog = source.catalog()
    keys = [meta.key for meta in catalog]
    assert keys
    assert len(set(keys)) == len(keys)
    assert all(meta.description for meta in catalog)


@pytest.mark.parametrize("step", [timedelta(minutes=m) for m in (5, 15, 20, 60)])
def test_shapes_land_exactly_on_the_requested_grid(source: ProfileSource, step: timedelta) -> None:
    for meta in source.catalog():
        begin = meta.coverage.start + timedelta(hours=6)
        grid = meta.coverage.with_step(step).sub(begin, begin + timedelta(hours=24))
        shape = source.shape(meta.key, grid)
        assert shape.grid == grid
        assert shape.quantity is Quantity.DIMENSIONLESS


def test_outside_the_coverage_is_an_error(source: ProfileSource) -> None:
    meta = source.catalog()[0]
    late = TimeGrid(
        start=meta.coverage.end - timedelta(hours=1),
        end=meta.coverage.end + timedelta(hours=1),
        step=timedelta(minutes=30),
    )
    with pytest.raises(CoverageError):
        source.shape(meta.key, late)


def test_unknown_keys_are_an_error(source: ProfileSource) -> None:
    with pytest.raises(UnknownProfileError):
        source.shape("no-such-profile", source.catalog()[0].coverage)


def test_every_source_plugs_into_the_resolver(source: ProfileSource) -> None:
    resolver = ProfileResolver({source.name: source})
    meta = source.catalog()[0]
    window = meta.coverage.sub(meta.coverage.start, meta.coverage.start + timedelta(hours=24))
    scaling = Nominal(annual_kwh=8760) if meta.unit is ProfileUnit.SHAPE else AsMeasured()
    power = resolver.power(
        Shaped(ref=ProfileRef(source=source.name, key=meta.key), scaling=scaling), window
    )
    assert power.quantity is Quantity.POWER_KW
    assert power.isclose(source.shape(meta.key, window).scaled(1.0, Quantity.POWER_KW))
