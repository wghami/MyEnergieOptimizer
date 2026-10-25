"""Time series: one value per step of a grid, tagged with what the value measures.

Profiles are held as **average power over the step** (``POWER_KW``): unlike energy, this does not
depend on the step length, which is what lets one profile serve any grid. Converting to energy
multiplies by the step length. Resampling uses one overlap-weighted method for any pair of grids:
intensive quantities (power, price, shapes) become time-weighted means, and energy is summed or
split in proportion to the overlap, so it is conserved exactly.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Self

import numpy as np
import numpy.typing as npt

from myenergy.domain.errors import CoverageError, SeriesError
from myenergy.domain.time import TimeGrid

type Values = npt.NDArray[np.float64]


class Quantity(StrEnum):
    """What a series measures, which decides how it combines and resamples."""

    POWER_KW = "kW"
    ENERGY_KWH = "kWh"
    PRICE_EUR_PER_KWH = "EUR/kWh"
    DIMENSIONLESS = "1"

    @property
    def extensive(self) -> bool:
        """True when values add up over time (energy), false for rates and shapes."""
        return self is Quantity.ENERGY_KWH


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class TimeSeries:
    """Read-only values on a grid.

    Raises:
        SeriesError: the values do not match the grid, or are not finite numbers.
    """

    grid: TimeGrid
    values: Values
    quantity: Quantity

    def __post_init__(self) -> None:
        """Copy the values into a read-only float array and check them."""
        array = np.array(self.values, dtype=np.float64, copy=True)
        if array.shape != (len(self.grid),):
            msg = f"{array.shape} values do not match a grid of {len(self.grid)} steps"
            raise SeriesError(msg)
        if not np.isfinite(array).all():
            msg = "a series holds only finite numbers (no NaN or infinity)"
            raise SeriesError(msg)
        array.setflags(write=False)
        object.__setattr__(self, "values", array)

    @classmethod
    def constant(cls, grid: TimeGrid, value: float, quantity: Quantity) -> Self:
        """The same value on every step."""
        return cls(grid=grid, values=np.full(len(grid), value), quantity=quantity)

    def __len__(self) -> int:
        """Number of steps."""
        return len(self.grid)

    def _same_grid(self, other: "TimeSeries", operation: str) -> None:
        if other.grid != self.grid:
            msg = f"cannot {operation} series on different grids; resample one first"
            raise SeriesError(msg)

    def __add__(self, other: "TimeSeries") -> "TimeSeries":
        """Step-by-step sum of two series of the same quantity on the same grid."""
        self._same_grid(other, "add")
        if other.quantity is not self.quantity:
            msg = f"cannot add {other.quantity} to {self.quantity}"
            raise SeriesError(msg)
        return TimeSeries(grid=self.grid, values=self.values + other.values, quantity=self.quantity)

    def __sub__(self, other: "TimeSeries") -> "TimeSeries":
        """Step-by-step difference of two series of the same quantity on the same grid."""
        return self + other.scaled(-1.0)

    def scaled(self, factor: float, quantity: Quantity | None = None) -> "TimeSeries":
        """Multiply by ``factor``; ``quantity`` re-tags the result (shape times kW is power)."""
        return TimeSeries(
            grid=self.grid, values=self.values * factor, quantity=quantity or self.quantity
        )

    def energy(self) -> "TimeSeries":
        """Energy per step (kWh) from average power (kW times step hours).

        Raises:
            SeriesError: the series is not power.
        """
        if self.quantity is not Quantity.POWER_KW:
            msg = f"energy() needs a {Quantity.POWER_KW} series, not {self.quantity}"
            raise SeriesError(msg)
        return self.scaled(self.grid.step_hours, Quantity.ENERGY_KWH)

    def power(self) -> "TimeSeries":
        """Average power per step (kW) from energy per step.

        Raises:
            SeriesError: the series is not energy.
        """
        if self.quantity is not Quantity.ENERGY_KWH:
            msg = f"power() needs a {Quantity.ENERGY_KWH} series, not {self.quantity}"
            raise SeriesError(msg)
        return self.scaled(1.0 / self.grid.step_hours, Quantity.POWER_KW)

    def total(self) -> float:
        """Sum over the grid (energy only: summing power or prices has no meaning).

        Raises:
            SeriesError: the series is not energy.
        """
        if not self.quantity.extensive:
            msg = f"total() is for energy; use time_mean() for {self.quantity}"
            raise SeriesError(msg)
        return float(self.values.sum())

    def time_mean(self) -> float:
        """Time-weighted mean over the grid (rates and shapes; all steps have equal length).

        Raises:
            SeriesError: the series is energy (use ``total()``).
        """
        if self.quantity.extensive:
            msg = "time_mean() is for rates and shapes; use total() for energy"
            raise SeriesError(msg)
        return float(self.values.mean())

    def resample(self, grid: TimeGrid) -> "TimeSeries":
        """These values on another grid, which must lie within this series' range.

        Raises:
            CoverageError: ``grid`` reaches outside this series' range.
        """
        if not self.grid.contains(grid):
            msg = (
                f"cannot resample to [{grid.start.isoformat()}, {grid.end.isoformat()}): the "
                f"series covers [{self.grid.start.isoformat()}, {self.grid.end.isoformat()})"
            )
            raise CoverageError(msg)
        source_edges = self.grid.edges_seconds()
        step_seconds = self.grid.step.total_seconds()
        density = self.values if self.quantity.extensive else self.values * step_seconds
        cumulative = np.concatenate(([0.0], np.cumsum(density)))
        offset = (grid.start - self.grid.start).total_seconds()
        target_edges = grid.edges_seconds() + offset
        integral = np.diff(np.interp(target_edges, source_edges, cumulative))
        values = integral if self.quantity.extensive else integral / grid.step.total_seconds()
        return TimeSeries(grid=grid, values=values, quantity=self.quantity)

    def isclose(self, other: "TimeSeries", *, rel: float = 1e-12, abs_: float = 1e-12) -> bool:
        """Same grid, same quantity, and values equal within tolerance."""
        return (
            other.grid == self.grid
            and other.quantity is self.quantity
            and bool(np.allclose(self.values, other.values, rtol=rel, atol=abs_))
        )
