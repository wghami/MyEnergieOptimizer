"""Deterministic synthetic shapes for tests, notebooks and quick studies.

Values depend only on the time and the seed, never on the requested window: each UTC day is
generated at 5-minute resolution with its own random generator (seed, day), then resampled. Every
shape is normalised to a mean of 1 over the reference year 2021, like an Enedis coefficient.
"""

import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
import numpy.typing as npt

from myenergy.domain.errors import CoverageError, UnknownProfileError
from myenergy.domain.profiles import ProfileKind, ProfileMeta, TimestampLabel
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid

NATIVE_STEP = timedelta(minutes=5)
COVERAGE = TimeGrid(
    start=datetime(2000, 1, 1, tzinfo=UTC), end=datetime(2100, 1, 1, tzinfo=UTC), step=NATIVE_STEP
)
REFERENCE_YEAR = TimeGrid(
    start=datetime(2021, 1, 1, tzinfo=UTC), end=datetime(2022, 1, 1, tzinfo=UTC), step=NATIVE_STEP
)
_DAY = timedelta(days=1)
STEPS_PER_DAY = _DAY // NATIVE_STEP
_NOISE_SIGMA = 0.1
type Curve = npt.NDArray[np.float64]


def _hours_and_days(grid: TimeGrid) -> tuple[Curve, Curve]:
    seconds = (
        grid.edges_seconds()[:-1]
        + grid.step.total_seconds() / 2
        + (grid.start - COVERAGE.start).total_seconds()
    )
    return (seconds / 3600) % 24, seconds / 86400


class SyntheticProfileSource:
    """Seeded household, clear-sky PV and constant shapes over 2000-2100."""

    def __init__(
        self,
        *,
        seed: int = 0,
        latitude: float = 48.85,
        longitude: float = 2.35,
        name: str = "synthetic",
    ) -> None:
        """Fix the seed and the location of the PV curve (default: Paris)."""
        self._name = name
        self._seed = seed
        self._latitude = math.radians(latitude)
        self._longitude = longitude
        self._curves = {
            "household": self._household,
            "pv-clear-sky": self._pv,
            "constant": self._constant,
        }
        self._scale = {
            key: 1.0 / float(curve(REFERENCE_YEAR).mean()) for key, curve in self._curves.items()
        }

    @property
    def name(self) -> str:
        """The source name used in ``ProfileRef.source``."""
        return self._name

    def catalog(self) -> Sequence[ProfileMeta]:
        """The three synthetic profiles."""
        kinds = {
            "household": ProfileKind.CONSUMPTION,
            "pv-clear-sky": ProfileKind.PRODUCTION,
            "constant": ProfileKind.CONSUMPTION,
        }
        descriptions = {
            "household": "morning and evening peaks, winter-heavy, with seeded noise",
            "pv-clear-sky": "clear-sky solar elevation at the configured location",
            "constant": "flat 1.0",
        }
        return tuple(
            ProfileMeta(
                key=k,
                kind=kinds[k],
                coverage=COVERAGE,
                label=TimestampLabel.START,
                description=descriptions[k],
            )
            for k in self._curves
        )

    def _noise(self, grid: TimeGrid) -> Curve:
        """Lognormal noise (mean 1), drawn per UTC day so it never depends on the window."""
        first_day = (grid.start - COVERAGE.start) // _DAY
        days = len(grid) // STEPS_PER_DAY
        draws = [
            np.random.default_rng([self._seed, first_day + day]).lognormal(
                -(_NOISE_SIGMA**2) / 2, _NOISE_SIGMA, STEPS_PER_DAY
            )
            for day in range(days)
        ]
        return np.concatenate(draws)

    def _household(self, grid: TimeGrid) -> Curve:
        hours, days = _hours_and_days(grid)
        local = (hours + 1) % 24  # UTC+1, close enough for a synthetic curve
        peaks = 0.8 * np.exp(-(((local - 7.5) / 1.0) ** 2)) + 1.4 * np.exp(
            -(((local - 19.5) / 1.5) ** 2)
        )
        season = 1 + 0.25 * np.cos(2 * np.pi * (days % 365.25 - 15) / 365.25)
        return (0.6 + peaks) * season

    def _pv(self, grid: TimeGrid) -> Curve:
        hours, days = _hours_and_days(grid)
        declination = math.radians(23.44) * np.sin(2 * np.pi * (284 + days % 365.25) / 365.25)
        hour_angle = np.radians(15 * (hours + self._longitude / 15 - 12))
        elevation = np.sin(self._latitude) * np.sin(declination) + np.cos(self._latitude) * np.cos(
            declination
        ) * np.cos(hour_angle)
        return np.clip(elevation, 0.0, None)

    def _constant(self, grid: TimeGrid) -> Curve:
        return np.ones(len(grid))

    def shape(self, key: str, grid: TimeGrid) -> TimeSeries:
        """The shape ``key`` on ``grid``, identical whatever window it is requested for.

        Raises:
            UnknownProfileError: no such synthetic profile.
            CoverageError: ``grid`` reaches outside 2000-2100.
        """
        if key not in self._curves:
            msg = f"source {self._name!r} has no profile {key!r} ({', '.join(self._curves)})"
            raise UnknownProfileError(msg)
        if not COVERAGE.contains(grid):
            span = f"{grid.start.isoformat()} to {grid.end.isoformat()}"
            msg = f"synthetic profiles cover 2000-2100, not {span}"
            raise CoverageError(msg)
        start = COVERAGE.start + (grid.start - COVERAGE.start) // _DAY * _DAY
        end = COVERAGE.start - ((COVERAGE.start - grid.end) // _DAY) * _DAY
        native = TimeGrid(start=start, end=end, step=NATIVE_STEP)
        curve = self._curves[key](native) * self._scale[key]
        if key == "household":
            curve = curve * self._noise(native)
        return TimeSeries(grid=native, values=curve, quantity=Quantity.DIMENSIONLESS).resample(grid)
