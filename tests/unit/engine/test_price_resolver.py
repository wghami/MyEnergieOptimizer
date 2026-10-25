"""Resolving a price book: applicable lines, concrete rates, order, and every problem at once."""

from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest

from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.adapters.pricebooks.toml_files import read_price_book, with_user_book
from myenergy.domain.contract import Contract
from myenergy.domain.errors import PriceBookError
from myenergy.domain.flows import FlowKind
from myenergy.domain.packs import TariffPack
from myenergy.domain.pricebooks import Inclusion, PriceBook, PriceLine, RateRef
from myenergy.domain.rates import RateUnit
from myenergy.domain.schedules import Schedule, TimeWindows
from myenergy.engine.pricebases import FIXED, ONCE, PER_KWH, PERCENT_OF, TIERED
from myenergy.engine.pricing import PriceBookResolver, PricingContext

FIXTURES = Path(__file__).parents[2] / "fixtures"
PACKS = TomlPackSource([builtin_packs(), FIXTURES / "packs"])
FRANCE = PACKS.pack("fr-household")
BASES = {b.name: b for b in (FIXED, PER_KWH, TIERED, PERCENT_OF, ONCE)}
RESOLVER = PriceBookResolver(BASES)
NIGHT = TimeWindows.parse("22:00-06:00")
BILL = (date(2024, 11, 18), date(2025, 11, 18))


def contract(**fields: str) -> Contract:
    return FRANCE.contract(
        subscribed_kva=6, fields={"fta": "CU4", "supply_option": "hp-hc", **fields}, off_peak=NIGHT
    )


def context(
    made: Contract,
    *,
    pack: TariffPack = FRANCE,
    start: date = BILL[0],
    end: date = BILL[1],
    schedules: Mapping[str, Schedule] | None = None,
    allow_to_verify: bool = False,
) -> PricingContext:
    return PricingContext(
        contract=made,
        pack=pack,
        rates=PACKS.rates(pack.name),
        start=start,
        end=end,
        schedules=schedules or {},
        allow_to_verify=allow_to_verify,
    )


def test_the_french_book_for_a_cu4_household() -> None:
    resolved = RESOLVER.resolve(PACKS.price_book("fr-household"), context(contract()))
    names = [r.line.name for r in resolved.lines]
    assert names.index("cta") > max(
        names.index(n) for n in ("turpe.management", "turpe.metering", "turpe.power")
    )
    assert names.index("vat.subscription") > names.index("cta")
    assert "turpe.energy.grid" not in names
    assert "excise.collective" not in names
    energy = resolved.line("turpe.energy")
    assert energy.inclusion is Inclusion.INCLUDED
    assert [dict(r.values)["period"] for r in energy.rates] == ["HCH", "HCB", "HPH", "HPB"]
    assert energy.boundaries == (date(2025, 2, 1), date(2025, 8, 1))
    assert resolved.line("vat.subscription").depends_on == ("cta",)
    assert resolved.line("vat.consumption").depends_on == ("excise",)
    with pytest.raises(PriceBookError, match=r"no applicable line 'turpe\.energy\.grid'"):
        resolved.line("turpe.energy.grid")


def test_a_collective_participant_needs_unverified_rates_allowed() -> None:
    member = contract(fta="CU4-AC", status="collective")
    book = PACKS.price_book("fr-household")
    with pytest.raises(PriceBookError, match=r"excise\.collective.*still to verify"):
        RESOLVER.resolve(book, context(member, start=date(2025, 3, 1), end=date(2025, 4, 1)))
    resolved = RESOLVER.resolve(
        book, context(member, start=date(2025, 3, 1), end=date(2025, 4, 1), allow_to_verify=True)
    )
    names = {r.line.name for r in resolved.lines}
    assert {"turpe.energy.grid", "turpe.energy.collective", "excise.collective"} <= names
    assert "turpe.energy" not in names


def test_a_user_book_on_the_pack_book() -> None:
    book, rates = with_user_book(
        PACKS, "fr-household", read_price_book(FIXTURES / "pricebooks" / "example-supplier.toml")
    )
    resolved = RESOLVER.resolve(
        book,
        PricingContext(contract=contract(), pack=FRANCE, rates=rates, start=BILL[0], end=BILL[1]),
    )
    supply = resolved.line("supply.energy")
    assert [str(r.key) for r in supply.rates] == [
        "supply.energy[option=hp-hc, period=HC]",
        "supply.energy[option=hp-hc, period=HP]",
    ]
    assert resolved.line("supply.subscription").boundaries == (date(2025, 8, 1),)
    assert resolved.line("feed-in").line.credit
    assert set(resolved.line("vat.consumption").depends_on) == {
        "supply.energy",
        "service.support",
        "excise",
    }


def test_without_a_user_book() -> None:
    book, rates = with_user_book(PACKS, "fr-household")
    assert book == PACKS.price_book("fr-household")
    assert rates is PACKS.rates("fr-household")


def test_named_schedules() -> None:
    weekend = Schedule(name="weekend", default="all")
    book = PriceBook(
        name="b",
        lines=(
            PriceLine(
                name="x",
                basis="per_kwh",
                flow=FlowKind.IMPORT,
                schedule="weekend",
                rate=RateRef("excise", (("category", "household"), ("origin", "grid"))),
            ),
        ),
    )
    resolved = RESOLVER.resolve(book, context(contract(), schedules={"weekend": weekend}))
    assert resolved.line("x").schedule is weekend


def problems_of(
    book: PriceBook,
    made: Contract | None = None,
    *,
    pack: TariffPack = FRANCE,
    start: date = BILL[0],
    end: date = BILL[1],
) -> list[str]:
    with pytest.raises(PriceBookError) as caught:
        RESOLVER.resolve(book, context(made or contract(), pack=pack, start=start, end=end))
    return list(caught.value.problems)


EXCISE = RateRef("excise", (("category", "household"), ("origin", "grid")))


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (
            (PriceLine(name="x", basis="magic"),),
            "no price basis 'magic' (bases: fixed, once, per_kwh, percent_of, tiered_per_kwh)",
        ),
        ((PriceLine(name="x", basis="per_kwh", rate=EXCISE),), "basis 'per_kwh' needs a flow"),
        (
            (PriceLine(name="x", basis="fixed", flow=FlowKind.IMPORT, rate=EXCISE),),
            "basis 'fixed' takes no flow",
        ),
        ((PriceLine(name="x", basis="fixed"),), "basis 'fixed' needs a rate"),
        (
            (
                PriceLine(
                    name="x", basis="per_kwh", flow=FlowKind.IMPORT, schedule="nope", rate=EXCISE
                ),
            ),
            "no schedule 'nope' (network, supply, none)",
        ),
        (
            (
                PriceLine(
                    name="x",
                    basis="per_kwh",
                    flow=FlowKind.IMPORT,
                    rate=RateRef("excise", (("p", "{period}"),)),
                ),
            ),
            "{period} needs a schedule",
        ),
        (
            (
                PriceLine(
                    name="x",
                    basis="per_kwh",
                    flow=FlowKind.IMPORT,
                    rate=RateRef("excise", (("p", "{colour}"),)),
                ),
            ),
            "no value for {colour}",
        ),
        (
            (PriceLine(name="x", basis="per_kwh", flow=FlowKind.IMPORT, rate=RateRef("nothing")),),
            "no rate nothing[]",
        ),
        (
            (PriceLine(name="x", basis="fixed", rate=EXCISE),),
            "is in EUR/kWh; fixed takes EUR/kVA/year, EUR/month, EUR/year",
        ),
        (
            (
                PriceLine(
                    name="x",
                    basis="percent_of",
                    params={"of": ["ghost"]},
                    rate=RateRef("cta", (("network", "distribution"),)),
                ),
            ),
            "refers to lines that do not apply or exist: ['ghost']",
        ),
        (
            (
                PriceLine(
                    name="a",
                    basis="percent_of",
                    params={"of": ["b"]},
                    rate=RateRef("cta", (("network", "distribution"),)),
                ),
                PriceLine(
                    name="b",
                    basis="percent_of",
                    params={"of": ["a"]},
                    rate=RateRef("cta", (("network", "distribution"),)),
                ),
            ),
            "in a circle: ['a', 'b']",
        ),
    ],
)
def test_problems_are_named(lines: tuple[PriceLine, ...], expected: str) -> None:
    found = problems_of(PriceBook(name="b", lines=lines))
    assert any(expected in problem for problem in found), found


def test_every_problem_is_reported_at_once() -> None:
    book = PriceBook(
        name="b", lines=(PriceLine(name="x", basis="magic"), PriceLine(name="y", basis="fixed"))
    )
    found = problems_of(book, start=date(2020, 1, 2), end=date(2020, 1, 1))
    assert found[0] == "the bill period 2020-01-02 -> 2020-01-01 is empty"
    assert len(found) == 3


def test_rates_must_cover_the_whole_period() -> None:
    found = problems_of(
        PACKS.price_book("fr-household"), start=date(2024, 7, 1), end=date(2024, 9, 1)
    )
    assert any("covers 2024-07-01" in problem for problem in found)


def test_a_pack_without_supply_options() -> None:
    day_night = PACKS.pack("day-night")
    made = day_night.contract(subscribed_kva=3)
    book = PriceBook(
        name="b",
        lines=(
            PriceLine(
                name="x", basis="per_kwh", flow=FlowKind.IMPORT, schedule="supply", rate=EXCISE
            ),
        ),
    )
    found = problems_of(book, made, pack=day_night)
    assert any("no supply options" in problem for problem in found)


def test_tiered_lines_expand_their_tiers() -> None:
    line = PriceLine(
        name="t",
        basis="tiered_per_kwh",
        flow=FlowKind.SUPPLIED,
        rate=RateRef("excise", (("category", "{tier}"), ("origin", "grid"))),
        params={
            "reset": "year",
            "tiers": [{"name": "household", "up_to_kwh": 100}, {"name": "other"}],
        },
    )
    found = problems_of(PriceBook(name="b", lines=(line,)))
    assert len(found) == 1
    assert "no rate excise[category=other, origin=grid]" in found[0]


class _Note:
    """A test-only basis that needs no rate (a line that only shows text, say)."""

    name = "note"
    units: frozenset[RateUnit] = frozenset()
    needs_flow = False

    def problems(self, line: PriceLine) -> list[str]:
        del line  # takes anything
        return []

    def expansions(self, line: PriceLine) -> Mapping[str, tuple[str, ...]]:
        del line  # no placeholder of its own
        return {}

    def depends_on(self, line: PriceLine, book: PriceBook) -> tuple[str, ...]:
        del line, book  # independent of other lines
        return ()


def test_a_basis_without_rates() -> None:
    resolver = PriceBookResolver({**BASES, "note": _Note()})
    book = PriceBook(name="b", lines=(PriceLine(name="n", basis="note"),))
    assert resolver.resolve(book, context(contract())).line("n").rates == ()
