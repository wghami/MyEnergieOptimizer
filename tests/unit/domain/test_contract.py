"""A contract refuses combinations the tariff does not allow."""

from decimal import Decimal

import pytest

from myenergy.domain.contract import (
    SEGMENT_BT_36,
    AccessContract,
    Contract,
    CustomerStatus,
    Fta,
    Meter,
    SupplyOption,
)
from myenergy.domain.errors import ContractError
from myenergy.domain.time_classes import OffPeakHours, TimeClassCalendar

HOURS = OffPeakHours.parse("22:00-06:00")


def test_a_peak_offpeak_household() -> None:
    contract = Contract(
        subscribed_kva=Decimal(6),
        supply_option=SupplyOption.PEAK_OFFPEAK,
        fta=Fta.CU4,
        off_peak=HOURS,
    )
    assert contract.subscribed_kva == Decimal(6)
    assert (contract.status, contract.access_contract, contract.meter) == (
        CustomerStatus.CONSUMER,
        AccessContract.SUPPLIER,
        Meter.METERED,
    )
    assert contract.segment == SEGMENT_BT_36
    assert contract.calendar() == TimeClassCalendar(HOURS)


def test_a_flat_contract_needs_no_off_peak_hours() -> None:
    contract = Contract(subscribed_kva=Decimal("9.5"), supply_option=SupplyOption.BASE, fta=Fta.LU)
    assert contract.off_peak.hours == 0


def test_power_is_converted_and_bounded() -> None:
    contract = Contract(subscribed_kva=36, supply_option=SupplyOption.BASE, fta=Fta.CU)  # pyright: ignore[reportArgumentType]  # an int is accepted and converted
    assert contract.subscribed_kva == Decimal(36)
    for kva in ("0", "-3", "36.1"):
        with pytest.raises(ContractError, match="subscribed power"):
            Contract(subscribed_kva=Decimal(kva), supply_option=SupplyOption.BASE, fta=Fta.CU)


@pytest.mark.parametrize(
    ("option", "fta", "hours"),
    [
        (SupplyOption.PEAK_OFFPEAK, Fta.CU, OffPeakHours()),
        (SupplyOption.BASE, Fta.CU4, OffPeakHours()),
        (SupplyOption.BASE, Fta.MUDT, OffPeakHours.parse("22:00-05:00")),
    ],
)
def test_time_of_use_needs_eight_off_peak_hours(
    option: SupplyOption, fta: Fta, hours: OffPeakHours
) -> None:
    with pytest.raises(ContractError, match="needs 8 off-peak hours"):
        Contract(subscribed_kva=Decimal(6), supply_option=option, fta=fta, off_peak=hours)


def test_collective_options_need_the_collective_status() -> None:
    with pytest.raises(ContractError, match="only open to collective"):
        Contract(
            subscribed_kva=Decimal(6),
            supply_option=SupplyOption.BASE,
            fta=Fta.CU4_AC,
            off_peak=HOURS,
        )
    contract = Contract(
        subscribed_kva=Decimal(6),
        supply_option=SupplyOption.BASE,
        fta=Fta.MU4_AC,
        off_peak=HOURS,
        status=CustomerStatus.COLLECTIVE,
    )
    assert contract.fta.collective
    assert contract.fta.time_of_use
    assert not Fta.LU.time_of_use
