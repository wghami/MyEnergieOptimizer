"""Asset kinds: what an asset of a given kind does, as a plugin (ADR 0009).

A site file names assets by kind (``consumer``, ``pv``, ...). Each kind is an ``AssetKind``
registered in the ``myenergy.asset_kinds`` entry-point group, built-ins included, so a third
party adds a kind (an EV, a heat pump, a battery) without editing this package.
"""

from typing import Protocol, runtime_checkable

from myenergy.domain.profiles import ProfileSpec
from myenergy.domain.series import TimeSeries
from myenergy.domain.sites import AssetRole, AssetSpec
from myenergy.domain.time import TimeGrid

ASSET_KINDS_GROUP = "myenergy.asset_kinds"


class PowerProfiles(Protocol):
    """Turns profile specs into kW series (``myenergy.engine.profiles.ProfileResolver``)."""

    def power(self, spec: ProfileSpec, grid: TimeGrid) -> TimeSeries:
        """Average power (kW) of ``spec`` on ``grid``."""
        ...


@runtime_checkable
class AssetKind(Protocol):
    """One kind of asset."""

    @property
    def name(self) -> str:
        """The kind's name, as written in site files."""
        ...

    @property
    def role(self) -> AssetRole:
        """Source, sink or storage."""
        ...

    def power(self, asset: AssetSpec, grid: TimeGrid, profiles: PowerProfiles) -> TimeSeries:
        """The asset's power on ``grid`` (kW).

        Non-negative for a source or a sink; signed for a storage (positive when it returns
        energy).

        Raises:
            SiteError: the asset lacks what the kind needs (a profile, an option).
        """
        ...
