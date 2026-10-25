"""Price books in TOML: lines, settings, a user's own dated prices, and pack books by extends."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.adapters.pricebooks import toml_files as module
from myenergy.adapters.pricebooks.toml_files import load_price_book, read_price_book, with_user_book
from myenergy.domain.flows import FlowKind
from myenergy.domain.pricebooks import Inclusion
from myenergy.domain.rates import RateKey, RateStatus, RateUnit

FIXTURES = Path(__file__).parents[2] / "fixtures"
PACKS = TomlPackSource([builtin_packs(), FIXTURES / "packs"])


def test_the_example_supplier_book() -> None:
    loaded = read_price_book(FIXTURES / "pricebooks" / "example-supplier.toml")
    assert not loaded.settings_given
    assert [line.name for line in loaded.book.lines] == [
        "supply.subscription",
        "supply.energy",
        "service.support",
        "feed-in",
    ]
    feed_in = loaded.book.line("feed-in")
    assert (feed_in.flow, feed_in.credit, feed_in.vat) == (FlowKind.SOLD, True, None)
    assert loaded.rates is not None
    version = loaded.rates.history(RateKey.of("feed-in")).on(date(2026, 1, 1))
    assert (version.value, version.unit, version.status) == (
        Decimal("0.04"),
        RateUnit.EUR_PER_KWH,
        RateStatus.USER,
    )
    assert version.source == "Example supplier price list (invented)"
    monthly = loaded.rates.history(RateKey.of("supply.subscription", kva="6", option="hp-hc"))
    assert monthly.unit is RateUnit.EUR_PER_MONTH


def test_the_module_example() -> None:
    assert module.__doc__ is not None
    example = module.__doc__.split("::")[1].split("Other line keys")[0].replace("\n    ", "\n")
    loaded = load_price_book(example)
    assert loaded.settings_given
    assert loaded.book.settings.proration_days == 365
    assert dict(loaded.book.inclusion) == {"network": Inclusion.INCLUDED}
    assert loaded.book.line("cta").params == {
        "of": ["turpe.management", "turpe.metering", "turpe.power"]
    }
    assert loaded.rates is not None


def test_settings_and_parameters() -> None:
    text = """
[book]
name = "x"
settings = { proration_days = "actual", rounding = 0.001, vat_on_rounded = false }
remove = ["cta"]

[[lines]]
name = "t"
basis = "tiered_per_kwh"
flow = "shared_in"
counterparty = "op"
inclusion = "included"
when = { status = ["collective"] }
reset = "year"
tiers = [{ name = "a", up_to_kwh = 100 }, { name = "b" }]
rate = { component = "c", selectors = { tier = "{tier}" } }
"""
    book = load_price_book(text).book
    assert book.settings.proration_days is None
    assert book.settings.rounding == Decimal("0.001")
    assert not book.settings.vat_on_rounded
    line = book.line("t")
    assert (line.counterparty, line.inclusion) == ("op", Inclusion.INCLUDED)
    assert line.when == (("status", frozenset({"collective"})),)
    assert line.params["reset"] == "year"
    assert book.remove == ("cta",)


def test_pack_books_follow_extends() -> None:
    french = PACKS.price_book("fr-household")
    study = PACKS.price_book("vat-study")
    assert study.name == "vat-study"
    assert [line.name for line in study.lines] == [line.name for line in french.lines]
    assert dict(study.inclusion) == {"network": Inclusion.ITEMISED}
    assert PACKS.price_book("vat-study") is study
    assert PACKS.price_book("day-night").lines == ()


def test_a_user_book_keeps_or_sets_settings() -> None:
    loaded = load_price_book(
        '[book]\nname = "me"\nsettings = { rounding = 1 }\n'.replace("1", "1.0")
    )
    book, _ = with_user_book(PACKS, "fr-household", loaded)
    assert book.settings.rounding == Decimal(1)
    plain, _ = with_user_book(PACKS, "fr-household", load_price_book('[book]\nname = "me"\n'))
    assert plain.settings == PACKS.price_book("fr-household").settings


RATES = """
[sources.s]
title = "t"

[[rates]]
component = "c"
unit = "EUR"

[[rates.versions]]
from = 2024-01-01
source = "s"
status = "user"
value = 1.0
"""


def write_pack(root: Path, book: str) -> Path:
    folder = root / "p"
    folder.mkdir()
    (folder / "pack.toml").write_text(
        '[pack]\nname = "p"\ntitle = "t"\nextends = "fr-household"\n', encoding="utf-8"
    )
    (folder / "price-book.toml").write_text(book, encoding="utf-8")
    return root


@pytest.mark.parametrize(
    ("book", "message"),
    [
        ('[book]\nname = "p"\n' + RATES, "takes no rates"),
        (
            '[book]\nname = "p"\nremove = ["nope"]\n',
            r"p/price-book.toml: book 'p' removes unknown lines \['nope'\]",
        ),
    ],
)
def test_broken_pack_books(tmp_path: Path, book: str, message: str) -> None:
    packs = TomlPackSource([builtin_packs(), write_pack(tmp_path, book)])
    with pytest.raises(DataFormatError, match=message):
        packs.price_book("p")


def test_repeated_lines_name_the_file() -> None:
    line = '[[lines]]\nname = "a"\nbasis = "fixed"\n'
    text = '[book]\nname = "x"\n' + line + line
    with pytest.raises(DataFormatError, match=r"mine\.toml: book 'x' repeats lines \['a'\]"):
        load_price_book(text, origin="mine.toml")
