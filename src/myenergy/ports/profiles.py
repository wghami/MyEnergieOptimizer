"""The port through which profile shapes are read (MEO-PLG-1, PRT-1)."""

from collections.abc import Sequence
from typing import Protocol

from myenergy.domain.profiles import ProfileMeta
from myenergy.domain.series import TimeSeries
from myenergy.domain.time import TimeGrid


class ProfileSource(Protocol):
    """A provider of dimensionless shapes (Enedis, CSV, synthetic…).

    Contract (``tests/contract/test_profile_sources.py``):

    - ``catalog()`` lists every profile, with keys unique within the source;
    - ``shape(key, grid)`` returns a ``DIMENSIONLESS`` series on exactly ``grid``, labelled by
      interval start whatever the native convention;
    - a ``grid`` outside the profile's coverage raises ``CoverageError``;
    - an unknown key raises ``UnknownProfileError``.
    """

    @property
    def name(self) -> str:
        """The source name used in ``ProfileRef.source``."""
        ...

    def catalog(self) -> Sequence[ProfileMeta]:
        """Every profile this source offers."""
        ...

    def shape(self, key: str, grid: TimeGrid) -> TimeSeries:
        """The shape of profile ``key`` on ``grid``."""
        ...
