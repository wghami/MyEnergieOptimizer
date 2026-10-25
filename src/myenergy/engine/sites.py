"""Resolve a site description into asset powers and meter flows (ADR 0009).

The resolver knows asset kinds only through their plugins and roles, so a new kind never changes
this module. Flows are built per step of the requested grid (see ``myenergy.domain.flows``).
"""

import warnings
from collections.abc import Mapping

from myenergy.domain.errors import SiteError, TariffWarning
from myenergy.domain.flows import SharedFlow, SiteFlows
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.sites import AssetRole, SiteSpec
from myenergy.domain.time import TimeGrid
from myenergy.ports.assets import AssetKind, PowerProfiles
from myenergy.ports.packs import PackSource

_SIGN = {AssetRole.SOURCE: 1.0, AssetRole.SINK: -1.0, AssetRole.STORAGE: 1.0}


class SiteResolver:
    """Asset powers and flows of sites, from the registered asset kinds."""

    def __init__(
        self, kinds: Mapping[str, AssetKind], profiles: PowerProfiles, packs: PackSource
    ) -> None:
        """Use these kinds (by name), this profile resolver and these tariff packs."""
        self._kinds = dict(kinds)
        self._profiles = profiles
        self._packs = packs

    def _kind(self, name: str) -> AssetKind:
        try:
            return self._kinds[name]
        except KeyError:
            known = ", ".join(sorted(self._kinds)) or "none"
            msg = f"no asset kind {name!r} (kinds: {known})"
            raise SiteError(msg) from None

    def powers(self, site: SiteSpec, grid: TimeGrid) -> dict[str, TimeSeries]:
        """Each asset's signed power on ``grid`` (kW: + produces, - consumes), by asset id.

        Raises:
            SiteError: an unknown kind, or a kind that returns something other than kW on
                ``grid``, or a negative power from a source or a sink.
        """
        found: dict[str, TimeSeries] = {}
        for asset in site.assets:
            kind = self._kind(asset.kind)
            power = kind.power(asset, grid, self._profiles)
            if power.quantity is not Quantity.POWER_KW or power.grid != grid:
                msg = f"kind {kind.name!r} returned {power.quantity.value} on another grid"
                raise SiteError(msg)
            if kind.role is not AssetRole.STORAGE and power.values.min(initial=0.0) < 0:
                msg = f"asset {asset.id!r}: a {kind.role.value} cannot have negative power"
                raise SiteError(msg)
            found[asset.id] = power.scaled(_SIGN[kind.role])
        return found

    def flows(self, site: SiteSpec, grid: TimeGrid) -> SiteFlows:
        """The site's meter flows on ``grid``, its shares included.

        Warns:
            TariffWarning: the site shares energy and ``grid``'s step differs from the step at
                which its tariff pack allocates shared energy.

        Raises:
            SiteError: see ``powers``.
            FlowError: shares above import or export, or other broken flow invariants.
        """
        shared = tuple(
            SharedFlow(
                share.direction,
                share.counterparty,
                self._profiles.power(share.profile, grid).energy(),
            )
            for share in site.shares
        )
        step = self._packs.pack(site.contract.pack).sharing_step
        if shared and step is not None and step != grid.step:
            message = (
                f"site {site.id!r}: pack {site.contract.pack!r} allocates shared energy every "
                f"{step}, but flows are computed every {grid.step}"
            )
            warnings.warn(message, TariffWarning, stacklevel=2)
        return SiteFlows.from_powers(site.id, list(self.powers(site, grid).values()), shared)
