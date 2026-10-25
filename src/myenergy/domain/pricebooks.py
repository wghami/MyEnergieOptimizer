"""Price books: what a bill charges, as data (ADR 0010).

A ``PriceBook`` is a list of ``PriceLine``. A line names its **basis** (how its amount is built:
``fixed``, ``per_kwh``, ``tiered_per_kwh``, ``percent_of``, ``once``; bases are plugins), the
**flow** it charges and the **schedule** whose periods split it, a **rate** found in dated rate
tables, a **VAT category**, whether it is a **credit** (revenue), and whether it is **itemised**
(added to the total) or **included** in other prices (shown as "of which", but not added: a
supplier that bundles the network tariff into its own prices).

Rate selectors are templates: ``{fta}`` takes the contract field ``fta``, ``{subscribed_kva}``
the subscribed power, ``{period}`` each period of the line's schedule, and a basis may add its own
(``{tier}``). One line therefore prices every period without being repeated.

A tariff pack ships the regulated lines; a user's book adds the supplier's lines and prices.
``merged`` puts a user book on a pack book: a line with the same name replaces the pack's, and
``remove`` drops lines by name.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from myenergy.domain.contract import Contract
from myenergy.domain.errors import PriceBookError
from myenergy.domain.flows import FlowKind
from myenergy.domain.packs import Condition
from myenergy.domain.rates import RateKey

_PLACEHOLDER = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
SUBSCRIBED_KVA = "subscribed_kva"
PERIOD = "period"


class Inclusion(StrEnum):
    """Whether a line adds to the bill's total."""

    ITEMISED = "itemised"
    """Charged: added to the total."""
    INCLUDED = "included"
    """Inside other prices: shown as "of which", not added; still a base for ``percent_of``."""


@dataclass(frozen=True, slots=True)
class RateRef:
    """A rate component and selector templates (``{field}``, ``{period}``, ...)."""

    component: str
    selectors: tuple[tuple[str, str], ...] = ()

    @property
    def placeholders(self) -> frozenset[str]:
        """Every ``{name}`` used in the selectors."""
        return frozenset(
            name for _, value in self.selectors for name in _PLACEHOLDER.findall(value)
        )

    def key(self, values: Mapping[str, str]) -> RateKey:
        """The concrete key once every placeholder has a value.

        Raises:
            PriceBookError: a placeholder without a value.
        """
        missing = sorted(self.placeholders - set(values))
        if missing:
            msg = f"rate {self.component}: no value for {', '.join('{' + m + '}' for m in missing)}"
            raise PriceBookError([msg])
        return RateKey.of(
            self.component,
            **{
                name: _PLACEHOLDER.sub(lambda m: values[m.group(1)], value)
                for name, value in self.selectors
            },
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PriceLine:
    """One line of a price book; see the module docstring."""

    name: str
    basis: str
    layer: str = ""
    payee: str = ""
    flow: FlowKind | None = None
    counterparty: str | None = None
    schedule: str | None = None
    """``network``, ``supply`` (the contract's schedules) or the name of a schedule."""
    rate: RateRef | None = None
    vat: str | None = None
    """The VAT category whose VAT line charges this line, or ``None``."""
    credit: bool = False
    inclusion: Inclusion | None = None
    """``None``: the book's default for the line's layer, else itemised."""
    when: Condition = ()
    params: Mapping[str, object] = field(default_factory=dict[str, object])
    """Basis-specific parameters (e.g. ``of`` for ``percent_of``, ``tiers`` for tiered prices)."""

    def __post_init__(self) -> None:
        """Check the names.

        Raises:
            PriceBookError: no name or basis, or a counterparty on a flow that has none.
        """
        if not self.name or not self.basis:
            raise PriceBookError([f"a price line needs a name and a basis, got {self.name!r}"])
        shared = {FlowKind.SHARED_IN, FlowKind.SHARED_OUT}
        if self.counterparty is not None and self.flow not in shared:
            raise PriceBookError([f"line {self.name!r}: only shared flows have a counterparty"])

    def applies_to(self, contract: Contract) -> bool:
        """Whether the line's ``when`` condition holds for ``contract``."""
        fields = contract.selectors
        return all(fields.get(name) in values for name, values in self.when)


@dataclass(frozen=True, slots=True)
class BookSettings:
    """How amounts are prorated and rounded."""

    proration_days: int | None = 365
    """Fixed charges are prorated by days / this; ``None``: by the actual length of each year."""
    rounding: Decimal = Decimal("0.01")
    """Each line is rounded to this (euros) at the end."""
    vat_on_rounded: bool = True
    """VAT is computed on rounded lines (else on exact amounts)."""

    def __post_init__(self) -> None:
        """Check the values.

        Raises:
            PriceBookError: a non-positive day count or rounding step.
        """
        if (self.proration_days is not None and self.proration_days <= 0) or self.rounding <= 0:
            raise PriceBookError(["proration days and rounding must be positive"])


@dataclass(frozen=True, slots=True, kw_only=True)
class PriceBook:
    """Named price lines, their layers' default inclusion, and settings."""

    name: str
    lines: tuple[PriceLine, ...] = ()
    inclusion: tuple[tuple[str, Inclusion], ...] = ()
    """Default inclusion per layer, e.g. ``(("network", Inclusion.INCLUDED),)``."""
    settings: BookSettings = field(default_factory=BookSettings)
    remove: tuple[str, ...] = ()
    """Lines of the book underneath to drop when this book is merged onto it."""

    def __post_init__(self) -> None:
        """Check names.

        Raises:
            PriceBookError: no name, or two lines with one name.
        """
        names = [line.name for line in self.lines]
        problems = [] if self.name else ["a price book needs a name"]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            problems.append(f"book {self.name!r} repeats lines {repeated}")
        if problems:
            raise PriceBookError(problems)
        object.__setattr__(self, "inclusion", tuple(sorted(self.inclusion)))

    def line(self, name: str) -> PriceLine:
        """The line called ``name``.

        Raises:
            PriceBookError: no such line.
        """
        for line in self.lines:
            if line.name == name:
                return line
        raise PriceBookError([f"book {self.name!r} has no line {name!r}"])

    def inclusion_of(self, line: PriceLine) -> Inclusion:
        """The line's own inclusion, else its layer's default, else itemised."""
        return line.inclusion or dict(self.inclusion).get(line.layer, Inclusion.ITEMISED)

    def merged(self, user: "PriceBook", *, settings: BookSettings | None = None) -> "PriceBook":
        """``user`` on top of this book: same-named lines replaced, ``user.remove`` dropped.

        Layer defaults merge (``user`` wins). Settings are ``settings`` when given, else this
        book's.

        Raises:
            PriceBookError: ``user`` removes a line this book does not have.
        """
        own = {line.name for line in self.lines}
        unknown = sorted(set(user.remove) - own)
        if unknown:
            raise PriceBookError([f"book {user.name!r} removes unknown lines {unknown}"])
        replaced = {line.name for line in user.lines}
        kept = [
            line
            for line in self.lines
            if line.name not in replaced and line.name not in user.remove
        ]
        return PriceBook(
            name=f"{self.name}+{user.name}",
            lines=(*kept, *user.lines),
            inclusion=tuple((dict(self.inclusion) | dict(user.inclusion)).items()),
            settings=settings or self.settings,
        )
