"""Turn profile specs into kilowatt series, from whichever source holds the shape."""

from collections.abc import Mapping
from datetime import timedelta

from myenergy.domain.errors import CalibrationError, UnknownProfileError
from myenergy.domain.profiles import (
    AsMeasured,
    Calibrated,
    ProfileMeta,
    ProfileRef,
    ProfileSpec,
    ProfileUnit,
    PVSystem,
)
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid
from myenergy.ports.profiles import ProfileSource


class ProfileResolver:
    """Resolve ``ProfileSpec`` values against the registered profile sources."""

    def __init__(self, sources: Mapping[str, ProfileSource]) -> None:
        """Index ``sources`` by name.

        Raises:
            UnknownProfileError: a source's name differs from its key in ``sources``.
        """
        for key, source in sources.items():
            if source.name != key:
                msg = f"source registered as {key!r} calls itself {source.name!r}"
                raise UnknownProfileError(msg)
        self._sources = dict(sources)

    def _source(self, ref: ProfileRef) -> ProfileSource:
        try:
            return self._sources[ref.source]
        except KeyError:
            known = ", ".join(sorted(self._sources)) or "none"
            msg = f"no profile source {ref.source!r} (registered: {known})"
            raise UnknownProfileError(msg) from None

    def shape(self, ref: ProfileRef, grid: TimeGrid) -> TimeSeries:
        """The shape of ``ref`` on ``grid``, with its ``time_shift`` applied."""
        source = self._source(ref)
        if ref.time_shift == timedelta(0):
            return source.shape(ref.key, grid)
        shifted = TimeGrid(
            start=grid.start - ref.time_shift,
            end=grid.end - ref.time_shift,
            step=grid.step,
            timezone=grid.timezone,
        )
        return TimeSeries(
            grid=grid, values=source.shape(ref.key, shifted).values, quantity=Quantity.DIMENSIONLESS
        )

    def meta(self, ref: ProfileRef) -> ProfileMeta:
        """What the source says about ``ref``.

        Raises:
            UnknownProfileError: the source has no such profile.
        """
        source = self._source(ref)
        for meta in source.catalog():
            if meta.key == ref.key:
                return meta
        msg = f"source {ref.source!r} has no profile {ref.key!r}"
        raise UnknownProfileError(msg)

    def power(self, spec: ProfileSpec, grid: TimeGrid) -> TimeSeries:
        """Average power (kW) of ``spec`` on ``grid``.

        Raises:
            CalibrationError: the scaling does not fit the profile's unit.
        """
        scaling = spec.scaling
        unit = self.meta(spec.ref).unit
        if isinstance(scaling, Calibrated):
            window = self.shape(spec.ref, scaling.window)
            unit_hours = window.time_mean() * scaling.window.span / timedelta(hours=1)
            factor = scaling.kw_per_unit(unit_hours)
        else:
            expected = ProfileUnit.KW if isinstance(scaling, AsMeasured) else ProfileUnit.SHAPE
            if unit is not expected:
                msg = (
                    f"{type(scaling).__name__} needs a profile in {expected.value!r}, but "
                    f"{spec.ref.source}/{spec.ref.key} is in {unit.value!r}"
                )
                raise CalibrationError(msg)
            base = scaling.nominal() if isinstance(scaling, PVSystem) else scaling
            factor = base.kw_per_unit()
        return self.shape(spec.ref, grid).scaled(factor, Quantity.POWER_KW)
