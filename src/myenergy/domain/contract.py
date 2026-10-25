"""A household's supply contract: what the network tariff and the taxes depend on.

Fixed charges depend on the subscribed power, the network option (FTA), the customer's status and
who holds the network-access contract. Energy is priced on **two schedules**: the network's four
time classes, from the connection's off-peak hours (``network_schedule()``), and the supplier's
own periods (``supply_schedule()``), which the user may define freely.
"""

import warnings
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from myenergy.domain.errors import ContractError, TariffWarning
from myenergy.domain.schedules import NO_WINDOWS, PeriodRule, Schedule, TimeWindows
from myenergy.domain.time_classes import (
    HIGH_SEASON,
    LOW_SEASON,
    OFF_PEAK_HOURS_PER_DAY,
    network_schedule,
    turpe_seasons,
)

SEGMENT_BT_36 = "BT<=36kVA"
"""The rate-table segment of low-voltage connections up to 36 kVA."""
MAX_KVA = Decimal(36)


class SupplyOption(StrEnum):
    """How the supplier prices energy."""

    BASE = "base"
    """One price at every hour."""
    PEAK_OFFPEAK = "hp-hc"
    """Peak and off-peak prices (Heures pleines / Heures creuses) on the connection's hours."""


class Fta(StrEnum):
    """Network option (formule tarifaire d'acheminement), chosen by the supplier per connection."""

    CU = "CU"
    """Short use, one price (derogatory under TURPE 7: meters that do not communicate)."""
    CU4 = "CU4"
    """Short use, four time classes."""
    MU4 = "MU4"
    """Medium use, four time classes."""
    MUDT = "MUDT"
    """Medium use, peak and off-peak (derogatory under TURPE 7)."""
    LU = "LU"
    """Long use, one price."""
    CU4_AC = "CU4-AC"
    """CU4 for collective self-consumption below one HTA/BT substation."""
    MU4_AC = "MU4-AC"
    """MU4 for collective self-consumption below one HTA/BT substation."""

    @property
    def time_of_use(self) -> bool:
        """Whether the option prices peak and off-peak hours differently."""
        return self not in {Fta.CU, Fta.LU}

    @property
    def collective(self) -> bool:
        """Whether the option is reserved to collective self-consumption."""
        return self in {Fta.CU4_AC, Fta.MU4_AC}


class CustomerStatus(StrEnum):
    """What the connection does, which sets the management component."""

    CONSUMER = "consumer"
    """Consumes only, or self-produces without injecting."""
    COLLECTIVE = "collective"
    """Takes part in a collective self-consumption operation."""
    PRODUCER_INJECTION = "producer-injection"
    """Self-produces and injects its surplus into the grid."""


class AccessContract(StrEnum):
    """Who holds the network-access contract."""

    SUPPLIER = "supplier"
    """The supplier, in a single contract (contrat unique): the usual household case."""
    USER = "user"
    """The user, directly with the network operator (CARD)."""


class Meter(StrEnum):
    """Whether the connection has a metering device."""

    METERED = "metered"
    UNMETERED = "unmetered"


@dataclass(frozen=True, slots=True, kw_only=True)
class Contract:
    """A BT <= 36 kVA supply contract.

    ``off_peak`` holds the connection's off-peak hours (all year, or the high season when
    ``low_season_off_peak`` is given). ``supply`` is the supplier's own schedule; without it, the
    ``supply_option`` gives one (``base``: one period; ``hp-hc``: ``HP`` and ``HC`` on the
    connection's off-peak hours).

    Raises:
        ContractError: the power is out of range, or a collective option without collective
            status.

    Warns:
        TariffWarning: a time-of-use option with other than 8 off-peak hours a day.
    """

    subscribed_kva: Decimal
    supply_option: SupplyOption
    fta: Fta
    off_peak: TimeWindows = NO_WINDOWS
    low_season_off_peak: TimeWindows | None = None
    supply: Schedule | None = None
    status: CustomerStatus = CustomerStatus.CONSUMER
    access_contract: AccessContract = AccessContract.SUPPLIER
    meter: Meter = Meter.METERED

    def __post_init__(self) -> None:
        """Check the contract against the tariff rules."""
        kva = Decimal(self.subscribed_kva)
        if not 0 < kva <= MAX_KVA:
            msg = f"subscribed power must be in (0, {MAX_KVA}] kVA, got {kva}"
            raise ContractError(msg)
        object.__setattr__(self, "subscribed_kva", kva)
        if self.fta.collective and self.status is not CustomerStatus.COLLECTIVE:
            msg = f"{self.fta.value} is only open to collective self-consumption participants"
            raise ContractError(msg)
        needs_hours = self.fta.time_of_use or (
            self.supply is None and self.supply_option is SupplyOption.PEAK_OFFPEAK
        )
        seasons = {
            HIGH_SEASON: self.off_peak,
            LOW_SEASON: self.low_season_off_peak or self.off_peak,
        }
        for season, hours in seasons.items():
            if needs_hours and hours.hours != OFF_PEAK_HOURS_PER_DAY:
                message = (
                    f"{self.fta.value} / {self.supply_option.value}: TURPE gives a BT <= 36 kVA "
                    f"connection {OFF_PEAK_HOURS_PER_DAY:g} off-peak hours a day; this contract "
                    f"has {hours} ({hours.hours:g} h) in the {season} season. Priced as given."
                )
                warnings.warn(message, TariffWarning, stacklevel=3)

    @property
    def segment(self) -> str:
        """The rate-table segment of this contract."""
        return SEGMENT_BT_36

    def network_schedule(self) -> Schedule:
        """The network's four time classes on this connection's off-peak hours."""
        return network_schedule(self.off_peak, self.low_season_off_peak)

    def supply_schedule(self) -> Schedule:
        """The supplier's periods: ``supply`` when given, else one from ``supply_option``."""
        if self.supply is not None:
            return self.supply
        if self.supply_option is SupplyOption.BASE:
            return Schedule(name="base", default="base")
        if self.low_season_off_peak is None:
            return Schedule(name="hp-hc", rules=(PeriodRule("HC", self.off_peak),), default="HP")
        return Schedule(
            name="hp-hc",
            rules=(
                PeriodRule("HC", self.off_peak, seasons=frozenset({HIGH_SEASON})),
                PeriodRule("HC", self.low_season_off_peak, seasons=frozenset({LOW_SEASON})),
            ),
            default="HP",
            seasons=turpe_seasons(),
        )
