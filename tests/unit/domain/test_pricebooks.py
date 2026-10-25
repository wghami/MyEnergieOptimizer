"""Price-book data: rate templates, lines, settings and the merge of a user book on a pack book."""

from decimal import Decimal

import pytest

from myenergy.domain.contract import Contract
from myenergy.domain.errors import PriceBookError
from myenergy.domain.flows import FlowKind
from myenergy.domain.pricebooks import BookSettings, Inclusion, PriceBook, PriceLine, RateRef
from myenergy.domain.rates import RateKey

REF = RateRef(
    "turpe.withdrawal.energy", (("fta", "{fta}"), ("time_class", "{period}"), ("x", "a-{fta}"))
)


def line(name: str, **extra: object) -> PriceLine:
    return PriceLine(name=name, basis="fixed", **extra)  # pyright: ignore[reportArgumentType]  # keyword overrides


def test_rate_templates() -> None:
    assert REF.placeholders == {"fta", "period"}
    assert REF.key({"fta": "CU4", "period": "HPH"}) == RateKey.of(
        "turpe.withdrawal.energy", fta="CU4", time_class="HPH", x="a-CU4"
    )
    with pytest.raises(PriceBookError, match=r"no value for \{period\}"):
        REF.key({"fta": "CU4"})


def test_lines() -> None:
    contract = Contract(pack="p", subscribed_kva=Decimal(6), fields=(("fta", "CU4"),))
    assert line("a", when=(("fta", frozenset({"CU4"})),)).applies_to(contract)
    assert not line("a", when=(("fta", frozenset({"LU"})),)).applies_to(contract)
    assert line("a").applies_to(contract)
    shared = PriceLine(name="s", basis="per_kwh", flow=FlowKind.SHARED_IN, counterparty="op")
    assert shared.counterparty == "op"
    with pytest.raises(PriceBookError, match="needs a name and a basis"):
        PriceLine(name="", basis="fixed")
    with pytest.raises(PriceBookError, match="only shared flows have a counterparty"):
        PriceLine(name="x", basis="per_kwh", flow=FlowKind.IMPORT, counterparty="op")


def test_settings() -> None:
    assert BookSettings().proration_days == 365
    for bad in ({"proration_days": 0}, {"rounding": Decimal(0)}):
        with pytest.raises(PriceBookError, match="must be positive"):
            BookSettings(**bad)  # pyright: ignore[reportArgumentType]  # parametrised


def test_books_and_inclusion() -> None:
    book = PriceBook(
        name="pack",
        lines=(
            line("a", layer="network"),
            line("b", layer="tax"),
            line("c", layer="network", inclusion=Inclusion.ITEMISED),
        ),
        inclusion=(("network", Inclusion.INCLUDED),),
    )
    assert book.inclusion_of(book.line("a")) is Inclusion.INCLUDED
    assert book.inclusion_of(book.line("b")) is Inclusion.ITEMISED
    assert book.inclusion_of(book.line("c")) is Inclusion.ITEMISED
    with pytest.raises(PriceBookError, match="has no line 'z'"):
        book.line("z")
    with pytest.raises(PriceBookError) as caught:
        PriceBook(name="", lines=(line("a"), line("a")))
    assert caught.value.problems == ("a price book needs a name", "book '' repeats lines ['a']")


def test_a_user_book_replaces_removes_and_adds() -> None:
    pack = PriceBook(
        name="pack",
        lines=(line("a"), line("b"), line("c")),
        inclusion=(("network", Inclusion.INCLUDED),),
    )
    user = PriceBook(
        name="me",
        lines=(line("b", layer="supply"), line("d")),
        inclusion=(("network", Inclusion.ITEMISED),),
        remove=("c",),
    )
    merged = pack.merged(user)
    assert merged.name == "pack+me"
    assert [ln.name for ln in merged.lines] == ["a", "b", "d"]
    assert merged.line("b").layer == "supply"
    assert dict(merged.inclusion) == {"network": Inclusion.ITEMISED}
    assert merged.settings == pack.settings
    assert pack.merged(
        user, settings=BookSettings(rounding=Decimal("0.001"))
    ).settings.rounding == Decimal("0.001")
    with pytest.raises(PriceBookError, match=r"removes unknown lines \['zz'\]"):
        pack.merged(PriceBook(name="me", remove=("zz",)))
