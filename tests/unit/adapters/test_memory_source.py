"""The in-memory source refuses inconsistent profiles (the base of the CSV and synthetic ones)."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from myenergy.adapters.profiles.memory import InMemoryProfileSource
from myenergy.domain.errors import SeriesError, UnknownProfileError
from myenergy.domain.profiles import ProfileKind, ProfileMeta, TimestampLabel
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid

START = datetime(2026, 1, 1, tzinfo=UTC)
GRID = TimeGrid(start=START, end=START + timedelta(hours=2), step=timedelta(hours=1))
META = ProfileMeta(
    key="a",
    kind=ProfileKind.CONSUMPTION,
    coverage=GRID,
    label=TimestampLabel.START,
    description="a",
)


def shape(quantity: Quantity = Quantity.DIMENSIONLESS, grid: TimeGrid = GRID) -> TimeSeries:
    return TimeSeries(grid=grid, values=np.ones(len(grid)), quantity=quantity)


def test_catalog_and_name() -> None:
    source = InMemoryProfileSource("mem", {"a": (META, shape())})
    assert source.name == "mem"
    assert source.catalog() == (META,)


@pytest.mark.parametrize(
    ("profiles", "error", "message"),
    [
        (
            {"b": (META, shape())},
            UnknownProfileError,
            "profile registered as 'b' is described as 'a'",
        ),
        (
            {"a": (META, shape(Quantity.POWER_KW))},
            SeriesError,
            "must be a dimensionless shape, not kW",
        ),
        (
            {"a": (META, shape(grid=GRID.sub(START, START + timedelta(hours=1))))},
            SeriesError,
            "the shape's grid differs from its declared coverage",
        ),
    ],
)
def test_inconsistent_profiles_are_refused(
    profiles: dict[str, tuple[ProfileMeta, TimeSeries]], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        InMemoryProfileSource("mem", profiles)


def test_unknown_key_message() -> None:
    with pytest.raises(UnknownProfileError, match="source 'mem' has no profile 'z'"):
        InMemoryProfileSource("mem", {"a": (META, shape())}).shape("z", GRID)
