"""Built-in price bases check their parameters and say what they depend on."""

from collections.abc import Mapping
from decimal import Decimal

import pytest

from myenergy.domain.flows import FlowKind
from myenergy.domain.pricebooks import Inclusion, PriceBook, PriceLine, RateRef
from myenergy.domain.rates import RateUnit
from myenergy.engine.pricebases import FIXED, ONCE, PER_KWH, PERCENT_OF, TIERED

TIER_RATE = RateRef("supply.energy", (("tier", "{tier}"),))


def line(basis: str, params: Mapping[str, object] | None = None, **extra: object) -> PriceLine:
    return PriceLine(name="x", basis=basis, params=dict(params or {}), **extra)  # pyright: ignore[reportArgumentType]  # keyword overrides


def test_simple_bases() -> None:
    assert FIXED.units == {RateUnit.EUR_PER_YEAR, RateUnit.EUR_PER_KVA_YEAR, RateUnit.EUR_PER_MONTH}
    assert (FIXED.needs_flow, PER_KWH.needs_flow, ONCE.needs_flow) == (False, True, False)
    assert ONCE.units == {RateUnit.EUR}
    plain = line("fixed")
    assert FIXED.problems(plain) == []
    assert FIXED.expansions(plain) == {}
    assert FIXED.depends_on(plain, PriceBook(name="b")) == ()
    assert FIXED.problems(line("fixed", {"of": ["a"]})) == [
        "line 'x': basis 'fixed' takes no ['of']"
    ]


GOOD_TIERS = {
    "reset": "year",
    "tiers": [
        {"name": "t1", "up_to_kwh": 1000},
        {"name": "t2", "up_to_kwh": Decimal(3000)},
        {"name": "t3"},
    ],
}


def test_tiered_prices() -> None:
    good = line("tiered_per_kwh", GOOD_TIERS, flow=FlowKind.SUPPLIED, rate=TIER_RATE)
    assert TIERED.problems(good) == []
    assert TIERED.expansions(good) == {"tier": ("t1", "t2", "t3")}
    assert TIERED.depends_on(good, PriceBook(name="b")) == ()


@pytest.mark.parametrize(
    ("params", "rate", "expected"),
    [
        ({**GOOD_TIERS, "reset": "decade"}, TIER_RATE, "reset must be one of"),
        ({**GOOD_TIERS, "colour": "red"}, TIER_RATE, "unknown parameters ['colour']"),
        (GOOD_TIERS, RateRef("supply.energy"), "must use {tier}"),
        ({"reset": "year"}, TIER_RATE, "tiers must be a non-empty list of tables"),
        ({"reset": "year", "tiers": ["t1"]}, TIER_RATE, "tiers must be a non-empty list of tables"),
        ({"reset": "year", "tiers": [{"name": "t"}, {"name": "t"}]}, TIER_RATE, "distinct name"),
        (
            {
                "reset": "year",
                "tiers": [{"name": "a", "up_to_kwh": 5}, {"name": "b", "up_to_kwh": 9}],
            },
            TIER_RATE,
            "up_to_kwh must rise",
        ),
        (
            {
                "reset": "year",
                "tiers": [
                    {"name": "a", "up_to_kwh": 9},
                    {"name": "b", "up_to_kwh": 5},
                    {"name": "c"},
                ],
            },
            TIER_RATE,
            "up_to_kwh must rise",
        ),
        (
            {"reset": "year", "tiers": [{"name": "a", "up_to_kwh": "lots"}, {"name": "b"}]},
            TIER_RATE,
            "up_to_kwh must rise",
        ),
    ],
)
def test_tier_problems(params: Mapping[str, object], rate: RateRef, expected: str) -> None:
    problems = TIERED.problems(line("tiered_per_kwh", params, flow=FlowKind.SUPPLIED, rate=rate))
    assert any(expected in problem for problem in problems), problems


def test_percentages_of_named_lines_or_a_vat_category() -> None:
    book = PriceBook(
        name="b",
        lines=(
            PriceLine(name="sub", basis="fixed", vat="subscription"),
            PriceLine(name="net", basis="fixed", vat="subscription", layer="network"),
            PriceLine(name="kwh", basis="per_kwh", vat="consumption"),
        ),
        inclusion=(("network", Inclusion.INCLUDED),),
    )
    named = line("percent_of", {"of": ["sub", "net"]})
    category = line("percent_of", {"of_vat": "subscription"})
    assert PERCENT_OF.problems(named) == PERCENT_OF.problems(category) == []
    assert PERCENT_OF.depends_on(named, book) == ("sub", "net")
    assert PERCENT_OF.depends_on(category, book) == ("sub",)  # included lines carry no VAT
    assert PERCENT_OF.expansions(named) == {}


@pytest.mark.parametrize(
    ("params", "extra", "expected"),
    [
        ({}, {}, "give either of"),
        ({"of": ["a"], "of_vat": "c"}, {}, "give either of"),
        ({"of": [1]}, {}, "give either of"),
        ({"of": ["a"], "colour": 1}, {}, "unknown parameters ['colour']"),
        ({"of": ["a"]}, {"flow": FlowKind.IMPORT}, "has no flow"),
    ],
)
def test_percentage_problems(
    params: Mapping[str, object], extra: Mapping[str, object], expected: str
) -> None:
    problems = PERCENT_OF.problems(line("percent_of", params, **extra))
    assert any(expected in problem for problem in problems), problems
