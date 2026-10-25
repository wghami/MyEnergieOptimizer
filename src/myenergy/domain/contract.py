"""A supply contract, as generic data: power, free fields, off-peak hours and two schedules.

Nothing here is specific to a country or an offer. What the fields mean, which values they may
take, and which rules apply to them come from a **tariff pack** (``myenergy.domain.packs``); the
pack also turns the contract into its network and supply schedules. Fields double as rate
selectors: a field ``fta = "CU4"`` selects the rates whose key has ``fta=CU4``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from myenergy.domain.errors import ContractError
from myenergy.domain.schedules import NO_WINDOWS, Schedule, TimeWindows


@dataclass(frozen=True, slots=True, kw_only=True)
class Contract:
    """One connection's contract under a tariff pack.

    Build it with ``TariffPack.contract(...)``, which checks it against the pack's rules and
    fills the pack's defaults.

    Raises:
        ContractError: no pack, a power that is not positive, or a field repeated.
    """

    pack: str
    subscribed_kva: Decimal
    fields: tuple[tuple[str, str], ...] = ()
    """Free fields, sorted by name (for example ``fta``, ``status``)."""
    off_peak: TimeWindows = NO_WINDOWS
    """The connection's off-peak hours, in every season without its own."""
    seasonal_off_peak: tuple[tuple[str, TimeWindows], ...] = ()
    """Off-peak hours of particular seasons of the pack's network schedule."""
    network: Schedule | None = None
    """An explicit network schedule, instead of the pack's."""
    supply: Schedule | None = None
    """The supplier's own schedule, instead of the pack's supply option."""

    def __post_init__(self) -> None:
        """Normalise and check the generic parts."""
        if not self.pack:
            msg = "a contract names its tariff pack"
            raise ContractError(msg)
        kva = Decimal(self.subscribed_kva)
        if not kva > 0:
            msg = f"subscribed power must be positive, got {kva} kVA"
            raise ContractError(msg)
        object.__setattr__(self, "subscribed_kva", kva)
        for name, pairs in (("field", self.fields), ("season", self.seasonal_off_peak)):
            keys = [key for key, _ in pairs]
            if len(set(keys)) != len(keys):
                msg = f"a contract repeats a {name}: {keys}"
                raise ContractError(msg)
        object.__setattr__(self, "fields", tuple(sorted(self.fields)))
        object.__setattr__(self, "seasonal_off_peak", tuple(sorted(self.seasonal_off_peak)))

    @property
    def selectors(self) -> Mapping[str, str]:
        """The fields, by name."""
        return dict(self.fields)

    def field(self, name: str) -> str:
        """The value of field ``name``.

        Raises:
            ContractError: the contract has no such field.
        """
        try:
            return self.selectors[name]
        except KeyError:
            msg = f"the contract has no field {name!r} (fields: {', '.join(self.selectors)})"
            raise ContractError(msg) from None

    def off_peak_for(self, season: str | None) -> TimeWindows:
        """Off-peak hours of ``season`` (its own, else the general ones)."""
        return dict(self.seasonal_off_peak).get(season or "", self.off_peak)
