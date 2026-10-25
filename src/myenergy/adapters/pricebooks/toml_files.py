"""Price books from TOML (ADR 0010).

The same format serves a tariff pack's regulated book (``price-book.toml`` in the pack folder)
and a user's book (a supplier's lines, with the supplier's dated prices in the same file)::

    [book]
    name = "my-supplier"
    remove = []                                   # lines of the pack's book to drop
    inclusion = { network = "included" }          # default per layer: itemised | included
    settings = { proration_days = 365, rounding = 0.01, vat_on_rounded = true }

    [[lines]]
    name = "supply.energy"
    layer = "supply"
    basis = "per_kwh"            # fixed | per_kwh | tiered_per_kwh | percent_of | once
    flow = "supplied"
    schedule = "supply"                           # network | supply | a named schedule
    rate = { component = "supply.energy", selectors = { period = "{period}" } }
    vat = "consumption"

    [[lines]]
    name = "cta"
    basis = "percent_of"
    of = ["turpe.management", "turpe.metering", "turpe.power"]   # or: of_vat = "subscription"
    rate = { component = "cta", selectors = { network = "distribution" } }
    vat = "subscription"

    [sources.my-offer]                            # a user's dated prices, as in rate files
    title = "My supplier's price list"

    [[rates]]
    component = "supply.energy"
    unit = "EUR/kWh"
    by = "period"

    [[rates.versions]]
    from = 2025-08-01
    source = "my-offer"
    status = "user"
    value = { HP = 0.2, HC = 0.15 }

Other line keys: ``payee``, ``counterparty`` (shared flows), ``credit = true`` (revenue),
``inclusion``, ``when = { field = [values] }``, and for tiered prices ``reset`` and ``tiers``.
Anything malformed is a ``DataFormatError`` naming the file.
"""

import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.rates.layered import LayeredRateSource
from myenergy.adapters.rates.toml_files import TomlRateSource
from myenergy.domain.errors import PriceBookError
from myenergy.domain.flows import FlowKind
from myenergy.domain.pricebooks import BookSettings, Inclusion, PriceBook, PriceLine, RateRef
from myenergy.ports.packs import PackSource
from myenergy.ports.rates import RateSource

MAX_BYTES = 512 * 1024
"""Price books are small; larger inputs are refused (SEC-1)."""
_RATE_TABLES = ("sources", "rates")

FlowName = Literal[
    "import", "export", "self_consumption", "shared_in", "shared_out", "supplied", "sold"
]
InclusionName = Literal["itemised", "included"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _Rate(_Strict):
    component: str = Field(min_length=1)
    selectors: dict[str, str] = Field(default_factory=dict[str, str])


class _Line(_Strict):
    name: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    layer: str = ""
    payee: str = ""
    flow: FlowName | None = None
    counterparty: str | None = None
    schedule: str | None = None
    rate: _Rate | None = None
    vat: str | None = None
    credit: bool = False
    inclusion: InclusionName | None = None
    when: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    of: list[str] | None = None
    of_vat: str | None = None
    reset: str | None = None
    tiers: list[dict[str, str | int | Decimal]] | None = None


class _Settings(_Strict):
    proration_days: int | Literal["actual"] = 365
    rounding: Decimal = Decimal("0.01")
    vat_on_rounded: bool = True


class _Book(_Strict):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9._+-]*$")
    remove: list[str] = Field(default_factory=list[str])
    inclusion: dict[str, InclusionName] = Field(default_factory=dict[str, InclusionName])
    settings: _Settings | None = None


class _File(_Strict):
    book: _Book
    lines: list[_Line] = Field(default_factory=list[_Line])


@dataclass(frozen=True, slots=True)
class LoadedBook:
    """A price book, the dated prices it carries (if any), and whether it set its settings."""

    book: PriceBook
    rates: RateSource | None
    settings_given: bool


def _line(raw: _Line) -> PriceLine:
    params = {
        name: value
        for name, value in (
            ("of", raw.of),
            ("of_vat", raw.of_vat),
            ("reset", raw.reset),
            ("tiers", raw.tiers),
        )
        if value is not None
    }
    return PriceLine(
        name=raw.name,
        basis=raw.basis,
        layer=raw.layer,
        payee=raw.payee,
        flow=None if raw.flow is None else FlowKind(raw.flow),
        counterparty=raw.counterparty,
        schedule=raw.schedule,
        rate=None
        if raw.rate is None
        else RateRef(raw.rate.component, tuple(sorted(raw.rate.selectors.items()))),
        vat=raw.vat,
        credit=raw.credit,
        inclusion=None if raw.inclusion is None else Inclusion(raw.inclusion),
        when=tuple((name, frozenset(values)) for name, values in sorted(raw.when.items())),
        params=params,
    )


def load_price_book(text: str, *, origin: str = "<text>") -> LoadedBook:
    """The price book in ``text``, with its own dated prices if it carries ``sources``/``rates``.

    Raises:
        DataFormatError: invalid TOML, an unknown key, or a book that breaks a rule.
    """
    try:
        document = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        msg = f"{origin}: not valid TOML: {error}"
        raise DataFormatError(msg) from None
    tables = {name: document.pop(name) for name in _RATE_TABLES if name in document}
    try:
        parsed = _File.model_validate(document)
    except ValidationError as error:
        msg = f"{origin}: {error}"
        raise DataFormatError(msg) from None
    raw = parsed.book
    settings = raw.settings
    try:
        book = PriceBook(
            name=raw.name,
            lines=tuple(_line(line) for line in parsed.lines),
            inclusion=tuple((layer, Inclusion(value)) for layer, value in raw.inclusion.items()),
            settings=BookSettings()
            if settings is None
            else BookSettings(
                proration_days=None
                if settings.proration_days == "actual"
                else settings.proration_days,
                rounding=settings.rounding,
                vat_on_rounded=settings.vat_on_rounded,
            ),
            remove=tuple(raw.remove),
        )
    except PriceBookError as error:
        msg = f"{origin}: {error}"
        raise DataFormatError(msg) from None
    rates = (
        TomlRateSource(documents=[(origin, tables)], name=raw.name) if "rates" in tables else None
    )
    return LoadedBook(book=book, rates=rates, settings_given=settings is not None)


def read_price_book(path: Path, *, max_bytes: int = MAX_BYTES) -> LoadedBook:
    """The price book in the TOML file at ``path``.

    Raises:
        DataFormatError: the file is too large, not UTF-8, or malformed (see ``load_price_book``).
    """
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        msg = f"{path.name}: {len(raw)} bytes, more than the {max_bytes} allowed"
        raise DataFormatError(msg)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        msg = f"{path.name}: not UTF-8: {error}"
        raise DataFormatError(msg) from None
    return load_price_book(text, origin=path.name)


def with_user_book(
    packs: PackSource, pack: str, user: LoadedBook | None = None
) -> tuple[PriceBook, RateSource]:
    """The pack's book with ``user``'s on top, and the pack's rates under ``user``'s prices.

    Raises:
        UnknownPackError: no such pack.
        PriceBookError: ``user`` removes a line the pack's book does not have.
    """
    book, rates = packs.price_book(pack), packs.rates(pack)
    if user is None:
        return book, rates
    merged = book.merged(user.book, settings=user.book.settings if user.settings_given else None)
    layers = [rates] if user.rates is None else [user.rates, rates]
    return merged, LayeredRateSource(f"{pack}+{user.book.name}", layers)
