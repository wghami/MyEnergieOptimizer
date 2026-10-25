"""Dated rates: keys, versions and histories refuse anything ambiguous (ADR 0006)."""

from datetime import date
from decimal import Decimal

import pytest

from myenergy.domain.errors import CoverageError, RateError, UnverifiedRateError
from myenergy.domain.rates import RateHistory, RateKey, RateStatus, RateUnit, RateVersion

KEY = RateKey.of("excise", category="household", origin="grid")


def version(
    start: date,
    end: date | None,
    value: str = "0.02998",
    status: RateStatus = RateStatus.OFFICIAL,
    unit: RateUnit = RateUnit.EUR_PER_KWH,
) -> RateVersion:
    return RateVersion(
        value=Decimal(value),
        unit=unit,
        valid_from=start,
        valid_to=end,
        source="a test document",
        status=status,
    )


def test_keys_sort_their_selectors() -> None:
    assert RateKey.of("excise", origin="grid", category="household") == KEY
    assert hash(RateKey.of("excise", origin="grid", category="household")) == hash(KEY)
    assert str(KEY) == "excise[category=household, origin=grid]"
    assert str(RateKey.of("cta")) == "cta[]"


def test_keys_need_a_component_and_distinct_selectors() -> None:
    with pytest.raises(RateError, match="needs a component"):
        RateKey("")
    with pytest.raises(RateError, match="repeats a selector"):
        RateKey("cta", (("network", "distribution"), ("network", "transport")))


def test_versions_check_their_period_value_and_source() -> None:
    with pytest.raises(RateError, match="empty validity period"):
        version(date(2025, 8, 1), date(2025, 8, 1))
    with pytest.raises(RateError, match="not finite"):
        version(date(2025, 8, 1), None, value="NaN")
    with pytest.raises(RateError, match="no source"):
        RateVersion(
            value=Decimal(1),
            unit=RateUnit.FRACTION,
            valid_from=date(2025, 8, 1),
            valid_to=None,
            source="",
            status=RateStatus.OFFICIAL,
        )


def test_a_version_covers_a_half_open_period() -> None:
    closed = version(date(2025, 2, 1), date(2025, 8, 1))
    assert closed.covers(date(2025, 2, 1))
    assert closed.covers(date(2025, 7, 31))
    assert not closed.covers(date(2025, 8, 1))
    assert not closed.covers(date(2025, 1, 31))
    assert version(date(2025, 8, 1), None).covers(date(2099, 1, 1))


def test_a_history_finds_the_version_of_a_day() -> None:
    history = RateHistory(
        KEY,
        [
            version(date(2025, 8, 1), None, "0.02998"),
            version(date(2025, 2, 1), date(2025, 8, 1), "0.03370"),
        ],
    )
    assert [v.valid_from for v in history] == [date(2025, 2, 1), date(2025, 8, 1)]
    assert history.unit is RateUnit.EUR_PER_KWH
    assert history.on(date(2025, 7, 31)).value == Decimal("0.03370")
    assert history.on(date(2025, 8, 1)).value == Decimal("0.02998")


def test_a_day_outside_every_version_is_an_error() -> None:
    history = RateHistory(
        KEY,
        [
            version(date(2025, 2, 1), date(2025, 3, 1)),
            version(date(2025, 4, 1), date(2025, 5, 1)),
        ],
    )
    for day in (date(2025, 1, 31), date(2025, 3, 15), date(2025, 5, 1)):
        with pytest.raises(CoverageError, match=r"known: 2025-02-01 → 2025-03-01, 2025-04-01"):
            history.on(day)


def test_unverified_versions_are_refused_unless_allowed() -> None:
    history = RateHistory(KEY, [version(date(2025, 3, 1), None, "0", RateStatus.TO_VERIFY)])
    with pytest.raises(UnverifiedRateError, match="still to verify"):
        history.on(date(2025, 6, 1))
    assert history.on(date(2025, 6, 1), allow_to_verify=True).value == 0


def test_histories_refuse_empty_mixed_or_overlapping_versions() -> None:
    with pytest.raises(RateError, match="has no version"):
        RateHistory(KEY, [])
    with pytest.raises(RateError, match="mixes units"):
        RateHistory(
            KEY,
            [
                version(date(2025, 2, 1), date(2025, 8, 1)),
                version(date(2025, 8, 1), None, unit=RateUnit.FRACTION),
            ],
        )
    with pytest.raises(RateError, match="overlaps"):
        RateHistory(
            KEY, [version(date(2025, 2, 1), date(2025, 9, 1)), version(date(2025, 8, 1), None)]
        )
    with pytest.raises(RateError, match="overlaps"):
        RateHistory(KEY, [version(date(2025, 2, 1), None), version(date(2025, 8, 1), None)])
