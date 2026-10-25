"""Profiles: where a load or production curve comes from, and how it becomes kilowatts.

A *shape* is a dimensionless curve whose mean is about 1 over a year (an Enedis coefficient, a
synthetic curve). A *scaling* turns it into power with **one constant factor**, so the same
profile serves any simulation period and any step (SPEC decision 7):

- ``Nominal(annual_kwh)``: factor = annual energy / 8760 h; year-to-year variation in the data is
  kept, as in reality;
- ``Calibrated(energy_kwh, window)``: factor = energy / energy of the shape over ``window``, which
  may be any period (a billing year starting in November, a month, a week);
- ``PVSystem(peak_kwp, specific_yield_kwh_per_kwp)``: a nominal annual energy, until a PV API
  computes production directly;
- ``AsMeasured()``: the source holds kW already (factor 1).

Shapes take ``Nominal``, ``PVSystem`` or ``Calibrated``; measured kW takes ``AsMeasured`` or
``Calibrated``. Any other pairing is refused, never guessed.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from myenergy.domain.errors import CalibrationError, UnknownProfileError
from myenergy.domain.time import TimeGrid

HOURS_PER_NOMINAL_YEAR = 8760.0
"""365 days. A leap year of data integrates to about 0.27 % more energy, which is kept."""


class ProfileKind(StrEnum):
    """Whether a profile draws or produces energy."""

    CONSUMPTION = "consumption"
    PRODUCTION = "production"


class ProfileUnit(StrEnum):
    """What a source's values are: a dimensionless shape to scale, or measured power."""

    SHAPE = "1"
    KW = "kW"


class TimestampLabel(StrEnum):
    """Which end of its interval a source's timestamps name (Enedis: the start)."""

    START = "start"
    END = "end"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProfileRef:
    """A profile in a source, optionally shifted in time on purpose (SPEC decision 10).

    A positive ``time_shift`` moves the curve later: the value used at ``t`` is the source's value
    at ``t - time_shift``. It must be a whole number of the grid's steps when used.

    Raises:
        UnknownProfileError: an empty source or key name.
    """

    source: str
    key: str
    time_shift: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        """Refuse empty names."""
        if not self.source or not self.key:
            msg = f"a profile reference needs a source and a key, got {self.source!r}/{self.key!r}"
            raise UnknownProfileError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProfileMeta:
    """What a source says about one of its profiles."""

    key: str
    kind: ProfileKind
    coverage: TimeGrid
    """The period the data covers, on its finest native step."""
    label: TimestampLabel
    description: str
    unit: ProfileUnit = ProfileUnit.SHAPE


def _positive(value: float, name: str) -> None:
    if not value > 0:
        msg = f"{name} must be positive, got {value}"
        raise CalibrationError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class Nominal:
    """``annual_kwh`` per nominal year (8760 h).

    Raises:
        CalibrationError: a non-positive energy.
    """

    annual_kwh: float

    def __post_init__(self) -> None:
        """Check the energy."""
        _positive(self.annual_kwh, "annual_kwh")

    def kw_per_unit(self) -> float:
        """Kilowatts per unit of shape."""
        return self.annual_kwh / HOURS_PER_NOMINAL_YEAR


@dataclass(frozen=True, slots=True, kw_only=True)
class Calibrated:
    """``energy_kwh`` over exactly ``window``.

    Raises:
        CalibrationError: a non-positive energy.
    """

    energy_kwh: float
    window: TimeGrid

    def __post_init__(self) -> None:
        """Check the energy."""
        _positive(self.energy_kwh, "energy_kwh")

    def kw_per_unit(self, shape_unit_hours: float) -> float:
        """Kilowatts per unit of shape, given the shape's integral over the window (unit-hours).

        Raises:
            CalibrationError: the shape has no positive energy over the window.
        """
        if not shape_unit_hours > 0:
            msg = (
                f"cannot calibrate on [{self.window.start.isoformat()}, "
                f"{self.window.end.isoformat()}): the shape integrates to {shape_unit_hours}"
            )
            raise CalibrationError(msg)
        return self.energy_kwh / shape_unit_hours


@dataclass(frozen=True, slots=True, kw_only=True)
class PVSystem:
    """A PV array of ``peak_kwp`` producing ``specific_yield_kwh_per_kwp`` per nominal year.

    Raises:
        CalibrationError: a non-positive peak power or yield.
    """

    peak_kwp: float
    specific_yield_kwh_per_kwp: float

    def __post_init__(self) -> None:
        """Check the parameters."""
        _positive(self.peak_kwp, "peak_kwp")
        _positive(self.specific_yield_kwh_per_kwp, "specific_yield_kwh_per_kwp")

    def nominal(self) -> Nominal:
        """The equivalent nominal annual energy."""
        return Nominal(annual_kwh=self.peak_kwp * self.specific_yield_kwh_per_kwp)


@dataclass(frozen=True, slots=True, kw_only=True)
class AsMeasured:
    """The source already holds kW (measured data, e.g. a meter export): factor 1."""

    def kw_per_unit(self) -> float:
        """Kilowatts per unit: the values are kW already."""
        return 1.0


type Scaling = Nominal | Calibrated | PVSystem | AsMeasured


@dataclass(frozen=True, slots=True, kw_only=True)
class Shaped:
    """A profile made of a shape and a scaling."""

    ref: ProfileRef
    scaling: Scaling


type ProfileSpec = Shaped
"""Every way to describe a profile; PV APIs will add a computed form (SPEC §6)."""
