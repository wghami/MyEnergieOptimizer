"""Layered rates: an upper layer hides the whole history of a key below it."""

from datetime import date
from decimal import Decimal

import pytest

from myenergy.adapters.rates.layered import LayeredRateSource
from myenergy.domain.errors import UnknownRateError
from myenergy.domain.rates import RateHistory, RateKey, RateStatus, RateUnit, RateVersion


class _Fixed:
    def __init__(self, name: str, values: dict[str, str]) -> None:
        self.name = name
        self._histories = {
            RateKey.of(key): RateHistory(
                RateKey.of(key),
                [
                    RateVersion(
                        value=Decimal(value),
                        unit=RateUnit.FRACTION,
                        valid_from=date(2024, 1, 1),
                        valid_to=None,
                        source=name,
                        status=RateStatus.OFFICIAL,
                    )
                ],
            )
            for key, value in values.items()
        }

    def catalog(self) -> list[RateKey]:
        return list(self._histories)

    def history(self, key: RateKey) -> RateHistory:
        return self._histories[key]


def test_upper_layers_hide_lower_ones() -> None:
    rates = LayeredRateSource(
        "study", [_Fixed("top", {"vat": "0.055"}), _Fixed("base", {"vat": "0.2", "cta": "0.15"})]
    )
    assert [str(key) for key in rates.catalog()] == ["cta[]", "vat[]"]
    assert rates.history(RateKey.of("vat")).on(date(2026, 1, 1)).source == "top"
    assert rates.history(RateKey.of("cta")).on(date(2026, 1, 1)).source == "base"
    with pytest.raises(UnknownRateError, match=r"no rate excise\[\] in study"):
        rates.history(RateKey.of("excise"))
