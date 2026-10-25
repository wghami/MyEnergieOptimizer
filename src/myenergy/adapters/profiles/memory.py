"""Shapes held in memory: the base of the CSV and synthetic sources, and a reference adapter."""

from collections.abc import Mapping, Sequence

from myenergy.domain.errors import SeriesError, UnknownProfileError
from myenergy.domain.profiles import ProfileMeta
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid


class InMemoryProfileSource:
    """A ``ProfileSource`` over start-labelled shapes already loaded in memory.

    Raises:
        SeriesError: a shape is not dimensionless, or does not sit on its declared coverage.
        UnknownProfileError: a profile's key differs from the key it is registered under.
    """

    def __init__(self, name: str, profiles: Mapping[str, tuple[ProfileMeta, TimeSeries]]) -> None:
        """Check and keep ``profiles`` (key → metadata and native shape)."""
        for key, (meta, shape) in profiles.items():
            if meta.key != key:
                msg = f"profile registered as {key!r} is described as {meta.key!r}"
                raise UnknownProfileError(msg)
            if shape.quantity is not Quantity.DIMENSIONLESS:
                msg = f"profile {key!r} must be a dimensionless shape, not {shape.quantity}"
                raise SeriesError(msg)
            if shape.grid != meta.coverage:
                msg = f"profile {key!r}: the shape's grid differs from its declared coverage"
                raise SeriesError(msg)
        self._name = name
        self._profiles = dict(profiles)

    @property
    def name(self) -> str:
        """The source name used in ``ProfileRef.source``."""
        return self._name

    def catalog(self) -> Sequence[ProfileMeta]:
        """Every profile, in registration order."""
        return tuple(meta for meta, _ in self._profiles.values())

    def shape(self, key: str, grid: TimeGrid) -> TimeSeries:
        """The shape of ``key`` resampled onto ``grid``.

        Raises:
            UnknownProfileError: no profile ``key`` in this source.
            CoverageError: ``grid`` reaches outside the profile's data.
        """
        try:
            _, native = self._profiles[key]
        except KeyError:
            msg = f"source {self._name!r} has no profile {key!r}"
            raise UnknownProfileError(msg) from None
        return native.resample(grid)
