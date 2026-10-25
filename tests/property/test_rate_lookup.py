"""A history returns the one version that covers a day, and refuses every other day."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from myenergy.domain.errors import CoverageError
from myenergy.domain.rates import RateHistory, RateKey, RateStatus, RateUnit, RateVersion

ORIGIN = date(2024, 8, 1)


@st.composite
def histories(draw: st.DrawFn) -> RateHistory:
    """Consecutive periods separated by optional gaps; the last one may stay open."""
    lengths = draw(st.lists(st.integers(1, 400), min_size=1, max_size=6))
    gaps = draw(st.lists(st.integers(0, 60), min_size=len(lengths), max_size=len(lengths)))
    open_end = draw(st.booleans())
    versions: list[RateVersion] = []
    start = ORIGIN
    for index, (length, gap) in enumerate(zip(lengths, gaps, strict=True)):
        last = index == len(lengths) - 1
        end = None if last and open_end else start + timedelta(days=length)
        versions.append(
            RateVersion(
                value=Decimal(index),
                unit=RateUnit.EUR_PER_KWH,
                valid_from=start,
                valid_to=end,
                source="generated",
                status=RateStatus.OFFICIAL,
            )
        )
        start = start + timedelta(days=length + gap)
    shuffled = draw(st.permutations(versions))
    return RateHistory(RateKey.of("generated"), shuffled)


@given(histories(), st.integers(-30, 3000))
def test_lookup_matches_the_covering_version(history: RateHistory, offset: int) -> None:
    day = ORIGIN + timedelta(days=offset)
    covering = [version for version in history if version.covers(day)]
    assert len(covering) <= 1
    if covering:
        assert history.on(day) == covering[0]
    else:
        with pytest.raises(CoverageError):
            history.on(day)
