"""The French price book resolves for every contract the pack allows, over every rate period."""

import itertools
from datetime import date

import pytest

from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.domain.schedules import TimeWindows
from myenergy.engine.pricebases import FIXED, ONCE, PER_KWH, PERCENT_OF, TIERED
from myenergy.engine.pricing import PriceBookResolver, PricingContext

PACKS = TomlPackSource([builtin_packs()])
FRANCE = PACKS.pack("fr-household")
RESOLVER = PriceBookResolver({b.name: b for b in (FIXED, PER_KWH, TIERED, PERCENT_OF, ONCE)})
FIELDS = {spec.name: spec.values for spec in FRANCE.fields}
COLLECTIVE = {"CU4-AC", "MU4-AC"}


@pytest.mark.parametrize(
    ("fta", "status", "contract", "meter"),
    [
        combination
        for combination in itertools.product(
            FIELDS["fta"], FIELDS["status"], FIELDS["contract"], FIELDS["meter"]
        )
        if combination[0] not in COLLECTIVE or combination[1] == "collective"
    ],
)
def test_every_allowed_contract_resolves_from_2024_08_to_today(
    fta: str, status: str, contract: str, meter: str
) -> None:
    made = FRANCE.contract(
        subscribed_kva=9,
        fields={
            "fta": fta,
            "status": status,
            "contract": contract,
            "meter": meter,
            "supply_option": "base",
        },
        off_peak=TimeWindows.parse("23:00-07:00"),
    )
    resolved = RESOLVER.resolve(
        PACKS.price_book("fr-household"),
        PricingContext(
            contract=made,
            pack=FRANCE,
            rates=PACKS.rates("fr-household"),
            start=date(2024, 8, 1),
            end=date(2026, 10, 1),
            allow_to_verify=status == "collective",
        ),
    )
    names = {line.line.name for line in resolved.lines}
    assert {"turpe.management", "turpe.metering", "turpe.power", "cta", "excise"} <= names
    assert {"vat.subscription", "vat.consumption"} <= names
    energy = "turpe.energy.grid" if fta in COLLECTIVE else "turpe.energy"
    assert resolved.line(energy).boundaries == (
        date(2025, 2, 1),
        date(2025, 8, 1),
        date(2026, 8, 1),
    )
