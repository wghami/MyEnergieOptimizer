"""Sites: what is installed behind one grid connection, described as data.

A ``SiteSpec`` lists **assets** by id and **kind** (``consumer``, ``pv``, later ``battery``,
``ev``, ...). What a kind does is a plugin (``myenergy.ports.assets.AssetKind``); the flows only
look at its **role**: a source produces, a sink consumes, a storage does either. Adding a
household, an EV or a battery is one more entry in a site file, never a change to the flow or
bill code (ADR 0009).
"""

from dataclasses import dataclass
from enum import StrEnum

from myenergy.domain.contract import Contract
from myenergy.domain.errors import SiteError
from myenergy.domain.profiles import ProfileSpec


class AssetRole(StrEnum):
    """What an asset does to the site's energy balance."""

    SOURCE = "source"
    """Produces energy (PV, a generator)."""
    SINK = "sink"
    """Consumes energy (a household, an EV, a heat pump)."""
    STORAGE = "storage"
    """Stores and returns energy (a battery); its power is signed."""


class ShareDirection(StrEnum):
    """Whether shared energy comes to the site or leaves it."""

    IN = "in"
    """Allocated to this site by a sharing scheme: part of what its meter imports."""
    OUT = "out"
    """Allocated to others: part of what its meter exports."""


@dataclass(frozen=True, slots=True, kw_only=True)
class AssetSpec:
    """One asset: an id unique in its site, a kind, and what the kind needs to compute its power."""

    id: str
    kind: str
    profile: ProfileSpec | None = None
    options: tuple[tuple[str, str], ...] = ()
    """Free options for the kind's plugin, as text."""

    def __post_init__(self) -> None:
        """Check the names.

        Raises:
            SiteError: an empty id or kind.
        """
        if not self.id or not self.kind:
            msg = f"an asset needs an id and a kind, got id={self.id!r}, kind={self.kind!r}"
            raise SiteError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class ShareSpec:
    """Energy shared with a counterparty (an operation, a neighbour), as a power profile."""

    direction: ShareDirection
    counterparty: str
    profile: ProfileSpec

    def __post_init__(self) -> None:
        """Check the counterparty.

        Raises:
            SiteError: no counterparty.
        """
        if not self.counterparty:
            msg = "a share needs a counterparty"
            raise SiteError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class SiteSpec:
    """A grid connection: its contract, its assets and the energy it shares."""

    id: str
    contract: Contract
    assets: tuple[AssetSpec, ...] = ()
    shares: tuple[ShareSpec, ...] = ()

    def __post_init__(self) -> None:
        """Check ids.

        Raises:
            SiteError: no id, two assets with one id, or two shares with one counterparty and
                direction.
        """
        if not self.id:
            msg = "a site needs an id"
            raise SiteError(msg)
        ids = [asset.id for asset in self.assets]
        if len(set(ids)) != len(ids):
            msg = f"site {self.id!r} repeats an asset id: {ids}"
            raise SiteError(msg)
        shares = [(share.direction, share.counterparty) for share in self.shares]
        if len(set(shares)) != len(shares):
            msg = f"site {self.id!r} shares twice with one counterparty in one direction"
            raise SiteError(msg)
