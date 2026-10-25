"""Built-in asset kinds, registered as entry points like any third party's (ADR 0009)."""

from myenergy.domain.errors import SiteError
from myenergy.domain.series import TimeSeries
from myenergy.domain.sites import AssetRole, AssetSpec
from myenergy.domain.time import TimeGrid
from myenergy.ports.assets import PowerProfiles


class ProfiledKind:
    """A source or a sink whose power is its profile (a household, a PV array)."""

    def __init__(self, name: str, role: AssetRole) -> None:
        """A kind called ``name`` with ``role``."""
        self.name = name
        self.role = role

    def power(self, asset: AssetSpec, grid: TimeGrid, profiles: PowerProfiles) -> TimeSeries:
        """The asset's profile in kW.

        Raises:
            SiteError: the asset has no profile, or has options this kind does not take.
        """
        if asset.profile is None:
            msg = f"asset {asset.id!r} of kind {self.name!r} needs a profile"
            raise SiteError(msg)
        if asset.options:
            given = dict(asset.options)
            msg = f"asset {asset.id!r}: kind {self.name!r} takes no options, got {given}"
            raise SiteError(msg)
        return profiles.power(asset.profile, grid)


CONSUMER = ProfiledKind("consumer", AssetRole.SINK)
PV = ProfiledKind("pv", AssetRole.SOURCE)
