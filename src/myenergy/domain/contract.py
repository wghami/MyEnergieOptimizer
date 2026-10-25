"""A household's supply contract: what the network tariff and the taxes depend on.

Fixed charges depend on the subscribed power, the network option (FTA), the customer's status and
who holds the network-access contract; energy charges depend on the time classes, which come from
the connection's off-peak hours (``myenergy.domain.time_classes``).
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from myenergy.domain.errors import ContractError
from myenergy.domain.time_classes import NO_OFF_PEAK, OffPeakHours, TimeClassCalendar

SEGMENT_BT_36 = "BT<=36kVA"
"""The rate-table segment of low-voltage connections up to 36 kVA."""
MAX_KVA = Decimal(36)
OFF_PEAK_HOURS_PER_DAY = 8.0
"""TURPE: a BT <= 36 kVA connection has 8 off-peak hours a day."""


class SupplyOption(StrEnum):
    """How the supplier prices energy."""

    BASE = "base"
    """One price at every hour."""
    PEAK_OFFPEAK = "hp-hc"
    """Peak and off-peak prices (Heures pleines / Heures creuses)."""


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

    Raises:
        ContractError: the power is out of range, off-peak hours are missing or not 8 hours a day
            where the options need them, or a collective option without collective status.
    """

    subscribed_kva: Decimal
    supply_option: SupplyOption
    fta: Fta
    off_peak: OffPeakHours = NO_OFF_PEAK
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
        needs_hours = self.fta.time_of_use or self.supply_option is SupplyOption.PEAK_OFFPEAK
        if needs_hours and self.off_peak.hours != OFF_PEAK_HOURS_PER_DAY:
            msg = (
                f"{self.fta.value} with the {self.supply_option.value} option needs "
                f"{OFF_PEAK_HOURS_PER_DAY:g} off-peak hours a day, got {self.off_peak} "
                f"({self.off_peak.hours:g} h)"
            )
            raise ContractError(msg)
        if self.fta.collective and self.status is not CustomerStatus.COLLECTIVE:
            msg = f"{self.fta.value} is only open to collective self-consumption participants"
            raise ContractError(msg)

    @property
    def segment(self) -> str:
        """The rate-table segment of this contract."""
        return SEGMENT_BT_36

    def calendar(self) -> TimeClassCalendar:
        """The time-class calendar of this connection."""
        return TimeClassCalendar(self.off_peak)
