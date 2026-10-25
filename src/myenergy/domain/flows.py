"""Energy flows at a site's meter: what bills charge.

The same kWh is priced differently depending on where it comes from and where it goes, so a bill
charges **flows**, not "consumption". ``SiteFlows`` holds, as kWh series on one grid:

- ``import`` and ``export``: what the meter records drawing from and injecting into the network;
- ``self_consumption``: production used on site, never seen by the meter;
- ``shared_in`` / ``shared_out``: the parts of import / export allocated by a sharing scheme to or
  from a **counterparty** (an operation, a neighbour);
- derived: ``supplied`` = import - shared_in (what the supplier sells) and ``sold`` = export -
  shared_out (what goes to the grid buyer).

Flows describe what meters and sharing schemes measure; what each costs is the price book's
business. Built from asset powers, flows depend on the grid's step: comparing production and
consumption over 30 minutes hides moments when the site both imported and exported, so coarse
steps show more self-consumption than really happens (see notebook 06).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import numpy.typing as npt

from myenergy.domain.errors import FlowError
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.sites import ShareDirection
from myenergy.domain.time import TimeGrid

TOLERANCE_KWH = 1e-9
"""Rounding noise allowed when checking that flows are non-negative and shares fit."""


class FlowKind(StrEnum):
    """The flows a price book can charge."""

    IMPORT = "import"
    EXPORT = "export"
    SELF_CONSUMPTION = "self_consumption"
    SHARED_IN = "shared_in"
    SHARED_OUT = "shared_out"
    SUPPLIED = "supplied"
    SOLD = "sold"


_SHARED = {FlowKind.SHARED_IN: ShareDirection.IN, FlowKind.SHARED_OUT: ShareDirection.OUT}


@dataclass(frozen=True, slots=True)
class SharedFlow:
    """Energy (kWh per step) shared with ``counterparty`` in ``direction``."""

    direction: ShareDirection
    counterparty: str
    energy: TimeSeries


def _energy(series: TimeSeries) -> TimeSeries:
    return series.energy() if series.quantity is Quantity.POWER_KW else series


@dataclass(frozen=True, slots=True)
class SiteFlows:
    """Metered and shared energy of one site; see the module docstring.

    Raises:
        FlowError: a series that is not energy or not on ``grid``, a negative value, a shared
            total above import or export, or one counterparty twice in one direction.
    """

    site: str
    grid: TimeGrid
    imported: TimeSeries
    exported: TimeSeries
    self_consumed: TimeSeries
    shared: tuple[SharedFlow, ...] = field(default=())

    def __post_init__(self) -> None:
        """Check every invariant."""
        named: dict[str, TimeSeries] = {
            FlowKind.IMPORT.value: self.imported,
            FlowKind.EXPORT.value: self.exported,
            FlowKind.SELF_CONSUMPTION.value: self.self_consumed,
        }
        for share in self.shared:
            named[f"shared {share.direction.value} {share.counterparty}"] = share.energy
        for name, series in named.items():
            if series.quantity is not Quantity.ENERGY_KWH or series.grid != self.grid:
                msg = f"site {self.site!r}: {name} must be kWh on the site's grid"
                raise FlowError(msg)
            if series.values.min(initial=0.0) < -TOLERANCE_KWH:
                step = int(np.argmin(series.values))
                msg = f"site {self.site!r}: {name} is negative at step {step}"
                raise FlowError(msg)
        keys = [(share.direction, share.counterparty) for share in self.shared]
        if len(set(keys)) != len(keys):
            msg = f"site {self.site!r} shares twice with one counterparty in one direction"
            raise FlowError(msg)
        metered = ((ShareDirection.IN, self.imported), (ShareDirection.OUT, self.exported))
        for direction, total in metered:
            excess = self._shared_values(direction) - total.values
            if excess.max(initial=0.0) > TOLERANCE_KWH:
                step = int(np.argmax(excess))
                which = "import" if direction is ShareDirection.IN else "export"
                msg = (
                    f"site {self.site!r}: shared {direction.value} exceeds {which} at "
                    f"{self.grid.local(step):%Y-%m-%d %H:%M %Z} by {excess[step]:.6g} kWh"
                )
                raise FlowError(msg)

    def _shared_values(self, direction: ShareDirection) -> npt.NDArray[np.float64]:
        total = np.zeros(len(self.grid))
        for share in self.shared:
            if share.direction is direction:
                total = total + share.energy.values
        return total

    def _series(self, values: npt.NDArray[np.float64]) -> TimeSeries:
        return TimeSeries(
            grid=self.grid, values=np.maximum(values, 0.0), quantity=Quantity.ENERGY_KWH
        )

    @property
    def counterparties(self) -> Mapping[ShareDirection, tuple[str, ...]]:
        """The counterparties of each direction."""
        return {
            direction: tuple(s.counterparty for s in self.shared if s.direction is direction)
            for direction in ShareDirection
        }

    def _values(self, kind: FlowKind) -> npt.NDArray[np.float64]:
        shared_in = self._shared_values(ShareDirection.IN)
        shared_out = self._shared_values(ShareDirection.OUT)
        return {
            FlowKind.IMPORT: self.imported.values,
            FlowKind.EXPORT: self.exported.values,
            FlowKind.SELF_CONSUMPTION: self.self_consumed.values,
            FlowKind.SHARED_IN: shared_in,
            FlowKind.SHARED_OUT: shared_out,
            FlowKind.SUPPLIED: self.imported.values - shared_in,
            FlowKind.SOLD: self.exported.values - shared_out,
        }[kind]

    def _shared(self, kind: FlowKind, counterparty: str) -> TimeSeries:
        direction = _SHARED.get(kind)
        if direction is None:
            msg = f"{kind.value} has no counterparty"
            raise FlowError(msg)
        for share in self.shared:
            if share.direction is direction and share.counterparty == counterparty:
                return share.energy
        msg = f"site {self.site!r} shares nothing {direction.value} with {counterparty!r}"
        raise FlowError(msg)

    def flow(self, kind: FlowKind, counterparty: str | None = None) -> TimeSeries:
        """The kWh series of ``kind``; for shared flows, one counterparty or (``None``) all.

        Raises:
            FlowError: a counterparty for a flow that has none, or an unknown counterparty.
        """
        if counterparty is not None:
            return self._shared(kind, counterparty)
        return self._series(self._values(kind))

    def totals(self) -> Mapping[FlowKind, float]:
        """Energy (kWh) over the grid of every flow kind."""
        return {kind: self.flow(kind).total() for kind in FlowKind}

    @classmethod
    def from_powers(
        cls, site: str, powers: Sequence[TimeSeries], shared: Sequence[SharedFlow] = ()
    ) -> "SiteFlows":
        """Flows of a site whose assets have these signed powers (kW: + produces, - consumes).

        Production and consumption are compared **per step of the grid**.

        Raises:
            FlowError: a power series that is not kW, or not on one common grid.
        """
        if not powers:
            msg = f"site {site!r} has no asset power to build flows from"
            raise FlowError(msg)
        grid = powers[0].grid
        if any(p.grid != grid or p.quantity is not Quantity.POWER_KW for p in powers):
            msg = f"site {site!r}: asset powers must be kW on one grid"
            raise FlowError(msg)
        stacked = np.vstack([p.values for p in powers])
        produced = np.clip(stacked, 0.0, None).sum(axis=0)
        consumed = np.clip(-stacked, 0.0, None).sum(axis=0)
        hours = grid.step_hours

        def energy(values: npt.NDArray[np.float64]) -> TimeSeries:
            return TimeSeries(grid=grid, values=values * hours, quantity=Quantity.ENERGY_KWH)

        return cls(
            site=site,
            grid=grid,
            imported=energy(np.clip(consumed - produced, 0.0, None)),
            exported=energy(np.clip(produced - consumed, 0.0, None)),
            self_consumed=energy(np.minimum(produced, consumed)),
            shared=tuple(shared),
        )

    @classmethod
    def measured(
        cls,
        site: str,
        imported: TimeSeries,
        exported: TimeSeries,
        self_consumed: TimeSeries | None = None,
        shared: Sequence[SharedFlow] = (),
    ) -> "SiteFlows":
        """Flows as a meter recorded them (kW or kWh); a step may hold both import and export.

        Raises:
            FlowError: see the class.
        """
        imported, exported = _energy(imported), _energy(exported)
        own = self_consumed or TimeSeries.constant(imported.grid, 0.0, Quantity.ENERGY_KWH)
        return cls(
            site=site,
            grid=imported.grid,
            imported=imported,
            exported=exported,
            self_consumed=_energy(own),
            shared=tuple(shared),
        )
