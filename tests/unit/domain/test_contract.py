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
from myenergy.domain.errors import ContractError, TariffWarning
from myenergy.domain.schedules import PeriodRule, Schedule, TimeWindows
from myenergy.domain.time_classes import network_schedule

HOURS = TimeWindows.parse("22:00-06:00")


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
    assert contract.network_schedule() == network_schedule(HOURS)
    assert contract.supply_schedule().periods == ("HC", "HP")


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
        (SupplyOption.PEAK_OFFPEAK, Fta.CU, TimeWindows()),
        (SupplyOption.BASE, Fta.CU4, TimeWindows()),
        (SupplyOption.BASE, Fta.MUDT, TimeWindows.parse("22:00-05:00")),
    ],
)
def test_other_than_eight_off_peak_hours_is_a_warning(
    option: SupplyOption, fta: Fta, hours: TimeWindows
) -> None:
    with pytest.warns(TariffWarning, match="8 off-peak hours a day"):
        contract = Contract(
            subscribed_kva=Decimal(6), supply_option=option, fta=fta, off_peak=hours
        )
    assert contract.off_peak == hours


def test_off_peak_hours_per_season() -> None:
    summer = TimeWindows.parse("02:00-06:00 11:00-15:00")
    contract = Contract(
        subscribed_kva=Decimal(6),
        supply_option=SupplyOption.PEAK_OFFPEAK,
        fta=Fta.CU4,
        off_peak=HOURS,
        low_season_off_peak=summer,
    )
    assert contract.network_schedule() == network_schedule(HOURS, summer)
    supply = contract.supply_schedule()
    assert supply.periods == ("HC", "HP")
    assert [season.name for season in supply.seasons] == ["high", "low"]
    with pytest.warns(TariffWarning, match=r"in the low season"):
        Contract(
            subscribed_kva=Decimal(6),
            supply_option=SupplyOption.BASE,
            fta=Fta.CU4,
            off_peak=HOURS,
            low_season_off_peak=TimeWindows.parse("11:00-17:00"),
        )


def test_a_supplier_schedule_replaces_the_option() -> None:
    ev = Schedule(
        name="ev",
        rules=(PeriodRule("super-off-peak", TimeWindows.parse("02:00-05:00")),),
        default="normal",
    )
    contract = Contract(
        subscribed_kva=Decimal(9), supply_option=SupplyOption.PEAK_OFFPEAK, fta=Fta.LU, supply=ev
    )
    assert contract.supply_schedule() is ev
    base = Contract(subscribed_kva=Decimal(9), supply_option=SupplyOption.BASE, fta=Fta.LU)
    assert base.supply_schedule().periods == ("base",)


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
