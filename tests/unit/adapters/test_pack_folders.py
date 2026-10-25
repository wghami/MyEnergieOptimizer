"""Packs are folders of data; a pack may extend another and redefine only what changes."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.packs import toml_files as module
from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.domain.errors import UnknownPackError, UnknownRateError
from myenergy.domain.packs import OffPeakTemplate, tagged
from myenergy.domain.rates import RateKey
from myenergy.domain.schedules import Schedule, TimeWindows

FIXTURES = Path(__file__).parents[2] / "fixtures" / "packs"
VAT = RateKey.of("vat", base="consumption")
CTA = RateKey.of("cta", network="distribution")


@pytest.fixture(scope="module")
def packs() -> TomlPackSource:
    return TomlPackSource([builtin_packs(), FIXTURES])


def test_every_pack_is_listed_and_tagged(packs: TomlPackSource) -> None:
    assert [pack.name for pack in packs.catalog()] == ["day-night", "fr-household", "vat-study"]
    assert [pack.name for pack in tagged(packs.catalog(), country="FR")] == [
        "fr-household",
        "vat-study",
    ]
    assert [pack.name for pack in tagged(packs.catalog(), purpose="research")] == ["vat-study"]


def test_the_french_household_pack(packs: TomlPackSource) -> None:
    pack = packs.pack("fr-household")
    assert pack.max_kva == Decimal(36)
    assert isinstance(pack.network, OffPeakTemplate)
    assert pack.network.season_names == ("high", "low")
    assert [field.name for field in pack.fields] == [
        "segment",
        "fta",
        "status",
        "contract",
        "meter",
        "supply_option",
    ]
    assert len(pack.checks) == 3
    assert len(packs.rates("fr-household").catalog()) == 56
    assert packs.schedules("fr-household") == {}


def test_a_pack_inherits_and_overrides(packs: TomlPackSource) -> None:
    study = packs.pack("vat-study")
    assert study.extends == "fr-household"
    assert study.tag("country") == "FR"
    assert study.tag("source") == "hypothetical"
    assert study.checks == ()
    assert next(f for f in study.fields if f.name == "status").values == ("consumer",)
    assert study.network == packs.pack("fr-household").network
    contract = study.contract(
        subscribed_kva=6,
        fields={"fta": "CU4", "supply_option": "hp-hc"},
        off_peak=TimeWindows.parse("22:00-05:00"),
    )
    assert contract.field("status") == "consumer"  # no warning: the study dropped the checks
    rates = packs.rates("vat-study")
    assert rates.history(VAT).on(date(2026, 1, 1)).value == Decimal("0.055")
    assert rates.history(CTA) is packs.rates("fr-household").history(CTA)
    assert packs.rates("vat-study") is rates  # read once
    with pytest.raises(UnknownRateError, match="no rate nothing"):
        rates.history(RateKey.of("nothing"))


def test_a_fixed_network_schedule_from_the_pack_folder(packs: TomlPackSource) -> None:
    pack = packs.pack("day-night")
    assert isinstance(pack.network, Schedule)
    assert pack.network.periods == ("night", "day")
    assert list(packs.schedules("day-night")) == ["day-night"]
    assert packs.rates("day-night").catalog() == []


def test_unknown_packs_are_named(packs: TomlPackSource) -> None:
    for call in (packs.pack, packs.rates, packs.schedules):
        with pytest.raises(
            UnknownPackError,
            match=r"no tariff pack 'nope' \(packs: day-night, fr-household, vat-study\)",
        ):
            call("nope")
    with pytest.raises(UnknownPackError, match=r"\(packs: none\)"):
        TomlPackSource([]).pack("nope")


def write_pack(root: Path, folder: str, text: str, schedules: str | None = None) -> Path:
    path = root / folder
    path.mkdir(parents=True)
    (path / "pack.toml").write_text(text, encoding="utf-8")
    if schedules is not None:
        (path / "schedules.toml").write_text(schedules, encoding="utf-8")
    return path


def header(name: str, extends: str | None = None) -> str:
    parent = f'extends = "{extends}"\n' if extends else ""
    return f'[pack]\nname = "{name}"\ntitle = "t"\n{parent}'


@pytest.mark.parametrize(
    ("packs_", "message"),
    [
        ({"a": header("x"), "b": header("x")}, "two packs are called 'x'"),
        ({"a": header("a", "ghost")}, "'a' extends 'ghost', which does not exist"),
        ({"a": header("a", "b"), "b": header("b", "a")}, "in a circle: a -> b -> a"),
        ({"a": header("a") + '[network]\nschedule = "s"\npeak = "P"\n'}, "not both"),
        ({"a": header("a") + '[network]\nschedule = "s"\n'}, "no schedule 's'"),
        (
            {"a": header("a") + '[fields.f]\nvalues = ["x"]\ndefault = "y"\n'},
            r"a/pack.toml: field 'f': default 'y'",
        ),
        (
            {
                "a": header("a")
                + '[network.seasons.w]\ndates = "11-01..03-31"\npeak = "P"\noff_peak = "O"\n'
            },
            "falls in no season",
        ),
    ],
)
def test_broken_packs_are_refused(tmp_path: Path, packs_: dict[str, str], message: str) -> None:
    for folder, text in packs_.items():
        write_pack(tmp_path, folder, text)
    with pytest.raises(DataFormatError, match=message):
        TomlPackSource([tmp_path])


def test_folders_without_pack_toml_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / "README.md").write_text("not a pack", encoding="utf-8")
    write_pack(tmp_path, "a", header("a") + '[network]\npeak = "day"\noff_peak = "night"\n')
    pack = TomlPackSource([tmp_path]).pack("a")
    assert isinstance(pack.network, OffPeakTemplate)
    assert pack.network.season_names == (None,)


def test_the_module_example_parses(tmp_path: Path) -> None:
    assert module.__doc__ is not None
    example = module.__doc__.split("::")[1].split("A pack that")[0].replace("\n    ", "\n")
    write_pack(
        tmp_path, "study", example.replace('extends = "fr-household"', 'extends = "fr-household"')
    )
    study = TomlPackSource([builtin_packs(), tmp_path]).pack("fr-household-vat-study")
    assert study.tag("purpose") == "research"
