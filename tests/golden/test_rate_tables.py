"""The packaged rate tables match the official texts (double entry) and their own arithmetic.

Reference values below were typed again from the CRE deliberations, the Enedis grid and the tax
texts cited in the TOML files, independently of the generated tables.
"""

from datetime import date
from decimal import Decimal

import pytest

from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.domain.rates import RateKey, RateStatus

RATES = TomlPackSource([builtin_packs()]).rates("fr-household")
BT = "BT<=36kVA"
DATES = [date(2024, 8, 1), date(2025, 2, 1), date(2025, 8, 1), date(2026, 8, 1)]
CLASSES = ("HPH", "HCH", "HPB", "HCB")


def value(day: date, component: str, **selectors: str) -> Decimal:
    return RATES.history(RateKey.of(component, **selectors)).on(day, allow_to_verify=True).value


@pytest.mark.parametrize(
    ("day", "power", "energy", "management", "metering"),
    [
        (date(2024, 8, 1), "9.36", ("6.96", "4.76", "1.48", "0.92"), "16.20", "20.88"),
        (date(2025, 2, 1), "10.08", ("7.50", "5.13", "1.60", "1.00"), "16.92", "22.44"),
        (date(2025, 8, 1), "10.11", ("7.49", "3.97", "1.66", "1.16"), "16.80", "22.00"),
        (date(2026, 8, 1), "10.42", ("7.72", "4.09", "1.71", "1.20"), "17.12", "22.67"),
    ],
)
def test_cu4_household_with_a_supplier_contract(
    day: date, power: str, energy: tuple[str, ...], management: str, metering: str
) -> None:
    assert value(day, "turpe.withdrawal.power", segment=BT, fta="CU4") == Decimal(power)
    for time_class, expected in zip(CLASSES, energy, strict=True):
        found = value(day, "turpe.withdrawal.energy", segment=BT, fta="CU4", time_class=time_class)
        assert found == Decimal(expected) / 100
    assert value(
        day, "turpe.management", segment=BT, status="consumer", contract="supplier"
    ) == Decimal(management)
    assert value(day, "turpe.metering", segment=BT, meter="metered") == Decimal(metering)


@pytest.mark.parametrize(
    ("day", "cta", "excise", "vat_subscription"),
    [
        (date(2024, 11, 18), "0.2193", "0.02100", "0.055"),
        (date(2025, 2, 1), "0.2193", "0.03370", "0.055"),
        (date(2025, 8, 1), "0.2193", "0.02998", "0.20"),
        (date(2026, 2, 1), "0.15", "0.03085", "0.20"),
        (date(2026, 8, 1), "0.15", "0.03062", "0.20"),
    ],
)
def test_taxes(day: date, cta: str, excise: str, vat_subscription: str) -> None:
    assert value(day, "cta", network="distribution") == Decimal(cta)
    assert value(day, "excise", category="household", origin="grid") == Decimal(excise)
    assert value(day, "vat", base="subscription") == Decimal(vat_subscription)
    assert value(day, "vat", base="consumption") == Decimal("0.20")


def test_collective_self_consumption_excise_is_zero_but_unverified() -> None:
    key = RateKey.of("excise", category="household", origin="collective")
    version = RATES.history(key).on(date(2025, 3, 1), allow_to_verify=True)
    assert version.value == 0
    assert version.status is RateStatus.TO_VERIFY
    for day in (date(2024, 11, 18), date(2025, 2, 15)):
        before = RATES.history(key).on(day, allow_to_verify=True).value
        assert before == value(day, "excise", category="household", origin="grid")


def test_turpe_is_official_and_continuous_from_2024_08_01() -> None:
    for key in RATES.catalog():
        if not key.component.startswith("turpe."):
            continue
        versions = RATES.history(key).versions
        assert [version.valid_from for version in versions] == DATES, key
        assert versions[-1].valid_to is None
        assert all(version.status is RateStatus.OFFICIAL for version in versions)


def test_turpe_6_rounds_fixed_coefficients_to_12_cents() -> None:
    """TURPE 6 publishes b, CG and CC in multiples of 0.12 €; a misread footnote breaks this."""
    twelve = Decimal("0.12")
    for key in RATES.catalog():
        if key.component not in {"turpe.withdrawal.power", "turpe.management", "turpe.metering"}:
            continue
        for version in RATES.history(key).versions[:2]:
            assert version.value % twelve == 0, (key, version.valid_from)


def test_turpe_7_rises_by_3_04_percent_on_2026_08_01() -> None:
    """CRE deliberation 2026-105: every withdrawal coefficient times 1.0304, rounded to the cent."""
    for key in RATES.catalog():
        if not key.component.startswith("turpe.withdrawal"):
            continue
        history = RATES.history(key)
        before, after = history.on(date(2025, 8, 1)).value, history.on(date(2026, 8, 1)).value
        cents = Decimal("0.0001") if key.component.endswith("energy") else Decimal("0.01")
        assert (before * Decimal("1.0304")).quantize(cents) == after, key
