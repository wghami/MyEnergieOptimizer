"""Every ``PackSource`` honours the same contract (PRT-1), including test-only ones (PRT-2)."""

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.adapters.rates.layered import LayeredRateSource
from myenergy.domain.errors import UnknownPackError
from myenergy.domain.packs import TariffPack
from myenergy.domain.schedules import Schedule
from myenergy.ports.packs import PackSource
from myenergy.ports.rates import RateSource

FIXTURES = Path(__file__).parents[1] / "fixtures" / "packs"


class MemoryPacks:
    """A test-only source, written against the port only."""

    def __init__(self) -> None:
        """One pack without rates."""
        self._pack = TariffPack(name="memory", title="in memory", tags=(("purpose", "test"),))

    def catalog(self) -> Sequence[TariffPack]:
        return [self._pack]

    def _known(self, name: str) -> None:
        if name != "memory":
            raise UnknownPackError(name)

    def pack(self, name: str) -> TariffPack:
        self._known(name)
        return self._pack

    def rates(self, name: str) -> RateSource:
        self._known(name)
        return LayeredRateSource(name, [])

    def schedules(self, name: str) -> Mapping[str, Schedule]:
        self._known(name)
        return {}


SOURCES: dict[str, Callable[[], PackSource]] = {
    "toml": lambda: TomlPackSource([builtin_packs(), FIXTURES]),
    "memory": MemoryPacks,
}


@pytest.fixture(params=sorted(SOURCES))
def source(request: pytest.FixtureRequest) -> PackSource:
    return SOURCES[request.param]()


def test_catalog_is_sorted_and_each_pack_resolves(source: PackSource) -> None:
    names = [pack.name for pack in source.catalog()]
    assert names == sorted(set(names))
    for pack in source.catalog():
        assert source.pack(pack.name) == pack
        assert pack.title
        source.rates(pack.name).catalog()
        assert all(
            isinstance(schedule, Schedule) for schedule in source.schedules(pack.name).values()
        )


def test_unknown_packs_are_an_error(source: PackSource) -> None:
    for call in (source.pack, source.rates, source.schedules):
        with pytest.raises(UnknownPackError):
            call("no-such-pack")
