"""The ``PackSource`` port: where tariff packs, their rates and their schedules come from.

Folders of TOML files today (built-in and user-written); a database later, for packs whose rates
an agent maintains (ADR 0006, ADR 0008).
"""

from collections.abc import Mapping, Sequence
from typing import Protocol

from myenergy.domain.packs import TariffPack
from myenergy.domain.schedules import Schedule
from myenergy.ports.rates import RateSource


class PackSource(Protocol):
    """A store of tariff packs."""

    def catalog(self) -> Sequence[TariffPack]:
        """Every pack, sorted by name (filter by tag with ``myenergy.domain.packs.tagged``)."""
        ...

    def pack(self, name: str) -> TariffPack:
        """The pack called ``name``.

        Raises:
            UnknownPackError: no such pack.
        """
        ...

    def rates(self, name: str) -> RateSource:
        """The rates of pack ``name``, those it inherits included.

        Raises:
            UnknownPackError: no such pack.
        """
        ...

    def schedules(self, name: str) -> Mapping[str, Schedule]:
        """The named schedules a pack ships (e.g. example offers), those it inherits included.

        Raises:
            UnknownPackError: no such pack.
        """
        ...
