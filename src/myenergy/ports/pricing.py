"""Price bases: how a price line's amount is built, as plugins (ADR 0010).

Built-in bases (``fixed``, ``per_kwh``, ``tiered_per_kwh``, ``percent_of``, ``once``) register in
the ``myenergy.price_bases`` entry-point group like any third party's, so a new kind of charge
(for example a power-overrun charge for businesses) needs no change to the core.
"""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from myenergy.domain.pricebooks import PriceBook, PriceLine
from myenergy.domain.rates import RateUnit

PRICE_BASES_GROUP = "myenergy.price_bases"


@runtime_checkable
class PriceBasis(Protocol):
    """One way of building a line's amount."""

    @property
    def name(self) -> str:
        """The basis name, as written in price books."""
        ...

    @property
    def units(self) -> frozenset[RateUnit]:
        """The rate units this basis accepts (empty: it takes no rate)."""
        ...

    @property
    def needs_flow(self) -> bool:
        """Whether the line must name a flow."""
        ...

    def problems(self, line: PriceLine) -> list[str]:
        """What is wrong with the line's basis parameters (empty when nothing is)."""
        ...

    def expansions(self, line: PriceLine) -> Mapping[str, tuple[str, ...]]:
        """Extra placeholders this basis fills in rate selectors, with their values."""
        ...

    def depends_on(self, line: PriceLine, book: PriceBook) -> tuple[str, ...]:
        """Names of the lines whose amounts this line is computed from."""
        ...
