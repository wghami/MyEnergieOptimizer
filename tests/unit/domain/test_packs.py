"""Tariff packs give contract fields their meaning: values, defaults, checks and schedules."""

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from myenergy.domain.contract import Contract
from myenergy.domain.errors import ContractError, ScheduleError, TariffWarning
from myenergy.domain.packs import (
    YEAR_ROUND,
    CheckLevel,
    ContractCheck,
    FieldSpec,
    OffPeakSeason,
    OffPeakTemplate,
    SupplyOption,
    TariffPack,
    tagged,
)
from myenergy.domain.schedules import PeriodRule, Schedule, Season, TimeWindows
from myenergy.domain.time import TimeGrid

PARIS = ZoneInfo("Europe/Paris")
NIGHT = TimeWindows.parse("22:00-06:00")
SEASONAL = OffPeakTemplate(
    (
        OffPeakSeason(Season.parse("high", "11-01..03-31"), "HPH", "HCH"),
        OffPeakSeason(Season.parse("low", "04-01..10-31"), "HPB", "HCB"),
    )
)
PACK = TariffPack(
    name="test",
    title="a test pack",
    tags=(("sector", "household"), ("country", "XX")),
    fields=(
        FieldSpec("option", ("flat", "tou")),
        FieldSpec("status", ("consumer", "collective"), "consumer"),
        FieldSpec("supply", ("single", "two")),
    ),
    max_kva=Decimal(36),
    checks=(
        ContractCheck(
            "collective needs tou",
            when=(("status", frozenset({"collective"})),),
            require=(("option", frozenset({"tou"})),),
        ),
        ContractCheck(
            "8 h is usual",
            CheckLevel.WARNING,
            when=(("option", frozenset({"tou"})),),
            off_peak_hours=8,
        ),
    ),
    network=SEASONAL,
    supply_field="supply",
    supply_options=(SupplyOption("single", single="base"), SupplyOption("two")),
)


def contract(**fields: str) -> Contract:
    return PACK.contract(
        subscribed_kva=6, fields={"option": "flat", "supply": "single", **fields}, off_peak=NIGHT
    )


def test_defaults_are_filled_and_tags_sorted() -> None:
    made = PACK.contract(subscribed_kva="6", fields={"option": "flat", "supply": "two"})
    assert made.selectors == {"option": "flat", "status": "consumer", "supply": "two"}
    assert made.pack == "test"
    assert PACK.tags == (("country", "XX"), ("sector", "household"))
    assert PACK.tag("country") == "XX"
    assert PACK.tag("purpose") is None


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"colour": "red"}, r"has no field \['colour'\]"),
        ({"option": "nope"}, r"option = 'nope' is not one of \['flat', 'tou'\]"),
        ({"status": "collective"}, "collective needs tou"),
    ],
)
def test_fields_and_error_checks(fields: dict[str, str], message: str) -> None:
    with pytest.raises(ContractError, match=message):
        contract(**fields)


def test_required_fields_power_and_seasons() -> None:
    with pytest.raises(ContractError, match="field 'option' is required"):
        PACK.contract(subscribed_kva=6, fields={"supply": "two"})
    with pytest.raises(ContractError, match="allows up to 36 kVA, got 37"):
        PACK.contract(subscribed_kva=37, fields={"option": "flat", "supply": "two"})
    with pytest.raises(ContractError, match=r"has no season \['summer'\]"):
        PACK.contract(
            subscribed_kva=6,
            fields={"option": "flat", "supply": "two"},
            seasonal_off_peak={"summer": NIGHT},
        )


def test_warning_checks_look_at_every_season() -> None:
    with pytest.warns(
        TariffWarning, match=r"8 h is usual \(off-peak hours in season low: 11:00-17:00, 6 h\)"
    ):
        PACK.contract(
            subscribed_kva=6,
            fields={"option": "tou", "supply": "two"},
            off_peak=NIGHT,
            seasonal_off_peak={"low": TimeWindows.parse("11:00-17:00")},
        )


def test_network_schedule_from_the_template() -> None:
    made = PACK.contract(
        subscribed_kva=6,
        fields={"option": "tou", "supply": "two"},
        off_peak=NIGHT,
        seasonal_off_peak={"low": TimeWindows.parse("02:00-06:00 11:00-15:00")},
    )
    schedule = PACK.network_schedule(made)
    assert schedule.periods == ("HCH", "HCB", "HPH", "HPB")
    start = datetime(2026, 3, 31, tzinfo=PARIS)
    weights = schedule.weights(
        TimeGrid(start=start, end=start + timedelta(days=2), step=timedelta(hours=1))
    )
    found = [weights.periods[int(i)] for i in weights.shares.argmax(axis=1)]
    assert found[:6] == ["HCH"] * 6
    assert found[24:26] == ["HPB"] * 2
    assert found[26:30] == ["HCB"] * 4
    supply = PACK.supply_schedule(made)
    assert supply.periods == ("HC", "HP")
    assert supply.name == "test/two"


def test_explicit_schedules_win() -> None:
    own = Schedule(name="own", default="x")
    made = PACK.contract(
        subscribed_kva=6, fields={"option": "flat", "supply": "single"}, network=own, supply=own
    )
    assert PACK.network_schedule(made) is own
    assert PACK.supply_schedule(made) is own
    single = PACK.contract(subscribed_kva=6, fields={"option": "flat", "supply": "single"})
    assert PACK.supply_schedule(single).periods == ("base",)


def test_a_fixed_network_and_no_supply_options() -> None:
    fixed = Schedule(name="day-night", rules=(PeriodRule("night", NIGHT),), default="day")
    pack = TariffPack(name="fixed", title="fixed", network=fixed)
    made = pack.contract(subscribed_kva=100)
    assert pack.network_schedule(made) is fixed
    with pytest.raises(
        ContractError, match="no supply options; give the contract a supply schedule"
    ):
        pack.supply_schedule(made)


def test_year_round_template_and_supply_option() -> None:
    pack = TariffPack(
        name="simple",
        title="simple",
        fields=(FieldSpec("supply", ("two",)),),
        supply_field="supply",
        supply_options=(SupplyOption("two", peak="day", off_peak="night"),),
    )
    made = pack.contract(subscribed_kva=6, fields={"supply": "two"}, off_peak=NIGHT)
    assert pack.network is YEAR_ROUND
    assert pack.network_schedule(made).periods == ("HC", "HP")
    assert pack.supply_schedule(made).periods == ("night", "day")
    fixed = TariffPack(
        name="fixed-two",
        title="fixed",
        fields=pack.fields,
        supply_field="supply",
        supply_options=pack.supply_options,
        network=Schedule(name="flat", default="all"),
    )
    assert fixed.supply_schedule(
        fixed.contract(subscribed_kva=6, fields={"supply": "two"})
    ).periods == ("night", "day")


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: FieldSpec("", ("a",)), "needs a name"),
        (lambda: FieldSpec("f", ()), "at least one value"),
        (lambda: FieldSpec("f", ("a",), "b"), "default 'b' is not one of"),
        (lambda: TariffPack(name="", title="t"), "needs a name"),
        (
            lambda: TariffPack(
                name="p", title="t", fields=(FieldSpec("f", ("a",)), FieldSpec("f", ("a",)))
            ),
            "repeats a field",
        ),
        (
            lambda: TariffPack(name="p", title="t", supply_field="s"),
            "supply field 's' must be a field",
        ),
        (lambda: OffPeakTemplate(()), "one year-round entry"),
        (
            lambda: OffPeakTemplate((OffPeakSeason(None, "a", "b"), OffPeakSeason(None, "a", "b"))),
            "one year-round entry",
        ),
        (
            lambda: OffPeakTemplate((*SEASONAL.seasons, OffPeakSeason(None, "a", "b"))),
            "one year-round entry",
        ),
    ],
)
def test_inconsistent_packs_are_refused(make: Callable[[], object], message: str) -> None:
    with pytest.raises(ContractError, match=message):
        make()


def test_template_seasons_must_cover_the_year() -> None:
    with pytest.raises(ScheduleError, match="falls in no season"):
        OffPeakTemplate((OffPeakSeason(Season.parse("winter", "11-01..03-31"), "P", "O"),))


def test_tagged() -> None:
    other = TariffPack(name="other", title="o", tags=(("country", "XX"), ("purpose", "research")))
    assert tagged([PACK, other], country="XX") == [PACK, other]
    assert tagged([PACK, other], country="XX", purpose="research") == [other]
    assert tagged([PACK, other], country="FR") == []
