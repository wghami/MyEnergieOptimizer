"""Sites written in TOML become site specs, with contracts checked against their packs."""

from decimal import Decimal
from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.adapters.sites import toml_files as module
from myenergy.adapters.sites.toml_files import load_sites, read_sites
from myenergy.domain.errors import TariffWarning
from myenergy.domain.profiles import AsMeasured, Nominal, PVSystem
from myenergy.domain.sites import ShareDirection

FIXTURES = Path(__file__).parents[2] / "fixtures"
PACKS = TomlPackSource([builtin_packs(), FIXTURES / "packs"])


def test_a_street_of_two_sites() -> None:
    sites = read_sites(FIXTURES / "sites" / "street.toml", PACKS)
    sunny, flat = sites["sunny"], sites["flat"]
    assert sunny.contract.field("status") == "collective"
    assert sunny.contract.subscribed_kva == Decimal(9)
    assert [(a.id, a.kind) for a in sunny.assets] == [("house", "consumer"), ("roof", "pv")]
    roof = sunny.assets[1].profile
    assert roof is not None
    assert roof.scaling == PVSystem(peak_kwp=6.0, specific_yield_kwh_per_kwp=1100.0)
    house = flat.assets[0].profile
    assert house is not None
    assert house.scaling == Nominal(annual_kwh=2000.0)
    assert house.ref.time_shift.total_seconds() == 3600


def test_the_module_example_with_a_supply_schedule_and_a_share() -> None:
    assert module.__doc__ is not None
    example = module.__doc__.split("::")[1].split("A profile gives")[0].replace("\n    ", "\n")
    example = example.replace('supply_schedule = "ev-offer"', "")
    home = load_sites(example, PACKS)["home"]
    share = home.shares[0]
    assert (share.direction, share.counterparty) == (ShareDirection.IN, "street-operation")
    assert share.profile.scaling == AsMeasured()
    assert home.contract.off_peak_for("low").hours == 8
    assert dict(home.assets[0].options) == {}


def test_a_supply_schedule_shipped_by_the_pack() -> None:
    text = (
        '[sites.x]\npack = "day-night"\n[sites.x.contract]\n'
        'subscribed_kva = 3\nsupply_schedule = "day-night"\n'
    )
    site = load_sites(text, PACKS)["x"]
    assert site.contract.supply is not None
    assert site.contract.supply.periods == ("night", "day")


def test_pack_warnings_reach_the_caller() -> None:
    text = (
        '[sites.x]\npack = "fr-household"\n[sites.x.contract]\nsubscribed_kva = 6\n'
        'off_peak = "22:00-05:00"\nfields = { fta = "CU4", supply_option = "base" }\n'
    )
    with pytest.warns(TariffWarning, match="7 h"):
        load_sites(text, PACKS)


@pytest.mark.parametrize(
    ("contract", "message"),
    [
        (
            'subscribed_kva = 6\nsupply_schedule = "none"',
            r"\[x\]: pack 'day-night' has no schedule 'none' \(day-night\)",
        ),
        (
            'subscribed_kva = 99\nfields = { fta = "LU", supply_option = "base" }',
            r"\[x\]: .*allows up to",
        ),
    ],
)
def test_broken_sites_name_the_site(contract: str, message: str) -> None:
    pack = "day-night" if "schedule" in contract else "fr-household"
    text = f'[sites.x]\npack = "{pack}"\n[sites.x.contract]\n{contract}\n'
    with pytest.raises(DataFormatError, match=message):
        load_sites(text, PACKS, origin="mine.toml")


def test_a_pack_without_schedules_names_none() -> None:
    text = (
        '[sites.x]\npack = "fr-household"\n[sites.x.contract]\nsubscribed_kva = 6\n'
        'fields = { fta = "LU", supply_option = "base" }\nsupply_schedule = "ev"\n'
    )
    with pytest.raises(DataFormatError, match=r"\(none\)"):
        load_sites(text, PACKS)
