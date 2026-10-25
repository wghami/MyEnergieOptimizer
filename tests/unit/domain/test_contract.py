"""A contract is generic data; its meaning comes from a tariff pack."""

from decimal import Decimal

import pytest

from myenergy.domain.contract import Contract
from myenergy.domain.errors import ContractError
from myenergy.domain.schedules import TimeWindows

NIGHT = TimeWindows.parse("22:00-06:00")


def test_fields_are_sorted_selectors() -> None:
    contract = Contract(
        pack="p",
        subscribed_kva=6,  # pyright: ignore[reportArgumentType]  # an int is accepted and converted
        fields=(("status", "consumer"), ("fta", "CU4")),
        off_peak=NIGHT,
        seasonal_off_peak=(("summer", TimeWindows.parse("11:00-17:00")), ("autumn", NIGHT)),
    )
    assert contract.subscribed_kva == Decimal(6)
    assert contract.fields == (("fta", "CU4"), ("status", "consumer"))
    assert contract.selectors == {"fta": "CU4", "status": "consumer"}
    assert contract.field("fta") == "CU4"
    assert contract.off_peak_for("summer") == TimeWindows.parse("11:00-17:00")
    assert contract.off_peak_for("winter") == NIGHT
    assert contract.off_peak_for(None) == NIGHT


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"pack": "", "subscribed_kva": Decimal(6)}, "names its tariff pack"),
        ({"pack": "p", "subscribed_kva": Decimal(0)}, "must be positive"),
        (
            {"pack": "p", "subscribed_kva": Decimal(6), "fields": (("a", "1"), ("a", "2"))},
            "repeats a field",
        ),
        (
            {
                "pack": "p",
                "subscribed_kva": Decimal(6),
                "seasonal_off_peak": (("s", NIGHT), ("s", NIGHT)),
            },
            "repeats a season",
        ),
    ],
)
def test_generic_rules(arguments: dict[str, object], message: str) -> None:
    with pytest.raises(ContractError, match=message):
        Contract(**arguments)  # pyright: ignore[reportArgumentType]  # parametrised keyword arguments


def test_unknown_fields_are_named() -> None:
    contract = Contract(pack="p", subscribed_kva=Decimal(3), fields=(("fta", "CU4"),))
    with pytest.raises(ContractError, match=r"no field 'status' \(fields: fta\)"):
        contract.field("status")
