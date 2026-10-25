"""Every ``RateSource`` honours the same contract (PRT-1), including test-only ones (PRT-2).

Add a source by adding a factory to ``SOURCES``; nothing else changes.
"""

from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal

import pytest

from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.domain.errors import UnknownRateError
from myenergy.domain.rates import RateHistory, RateKey, RateStatus, RateUnit, RateVersion
from myenergy.ports.rates import RateSource


class MemoryRates:
    """A test-only source, written against the port only."""

    name = "memory"

    def __init__(self) -> None:
        """One CTA version."""
        key = RateKey.of("cta", network="distribution")
        version = RateVersion(
            value=Decimal("0.15"),
            unit=RateUnit.FRACTION,
            valid_from=date(2026, 2, 1),
            valid_to=None,
            source="test",
            status=RateStatus.OFFICIAL,
        )
        self._histories = {key: RateHistory(key, [version])}

    def catalog(self) -> Sequence[RateKey]:
        return list(self._histories)

    def history(self, key: RateKey) -> RateHistory:
        try:
            return self._histories[key]
        except KeyError:
            raise UnknownRateError(str(key)) from None


SOURCES: dict[str, Callable[[], RateSource]] = {
    "fr-household": lambda: TomlPackSource([builtin_packs()]).rates("fr-household"),
    "memory": MemoryRates,
}


@pytest.fixture(params=sorted(SOURCES))
def source(request: pytest.FixtureRequest) -> RateSource:
    return SOURCES[request.param]()


def test_keys_are_unique_and_each_has_its_history(source: RateSource) -> None:
    keys = source.catalog()
    assert keys
    assert len(set(keys)) == len(keys)
    for key in keys:
        assert source.history(key).key == key


def test_one_component_has_one_unit(source: RateSource) -> None:
    units: dict[str, set[RateUnit]] = {}
    for key in source.catalog():
        units.setdefault(key.component, set()).add(source.history(key).unit)
    assert all(len(found) == 1 for found in units.values()), units


def test_every_version_cites_a_source(source: RateSource) -> None:
    assert all(version.source for key in source.catalog() for version in source.history(key))


def test_unknown_keys_are_an_error(source: RateSource) -> None:
    with pytest.raises(UnknownRateError):
        source.history(RateKey.of("no-such-component"))
