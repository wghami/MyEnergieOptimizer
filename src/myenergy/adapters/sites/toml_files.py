"""Sites from TOML: a contract under a tariff pack, assets by kind, and shared energy (ADR 0009).

One file may describe several sites (a community is several sites)::

    [sites.home]
    pack = "fr-household"

    [sites.home.contract]
    subscribed_kva = 6
    off_peak = "22:00-06:00"                      # as printed on a bill
    seasonal_off_peak = { low = "02:00-06:00 11:00-15:00" }   # optional
    fields = { fta = "CU4", supply_option = "hp-hc" }
    supply_schedule = "ev-offer"                  # optional: a schedule shipped by the pack

    [[sites.home.assets]]
    id = "house"
    kind = "consumer"
    profile = { source = "synthetic", key = "household", annual_kwh = 3500 }

    [[sites.home.assets]]
    id = "roof"
    kind = "pv"
    profile = { source = "synthetic", key = "pv-clear-sky", peak_kwp = 3, yield_kwh_per_kwp = 1100 }

    [[sites.home.shares]]
    direction = "in"
    counterparty = "street-operation"
    profile = { source = "csv", key = "allocated", as_measured = true }

A profile gives its source and key, an optional ``time_shift_minutes``, and exactly one scaling:
``annual_kwh``, ``peak_kwp`` with ``yield_kwh_per_kwp``, or ``as_measured = true``. Anything
malformed is a ``DataFormatError`` naming the file and the site.
"""

import tomllib
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from myenergy.adapters.errors import DataFormatError
from myenergy.domain.errors import DomainError
from myenergy.domain.profiles import AsMeasured, Nominal, ProfileRef, PVSystem, Scaling, Shaped
from myenergy.domain.schedules import TimeWindows
from myenergy.domain.sites import AssetSpec, ShareDirection, ShareSpec, SiteSpec
from myenergy.ports.packs import PackSource

MAX_BYTES = 256 * 1024
"""Site files are small; larger inputs are refused (SEC-1)."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _Profile(_Strict):
    source: str
    key: str
    time_shift_minutes: int = 0
    annual_kwh: float | int | None = None
    peak_kwp: float | int | None = None
    yield_kwh_per_kwp: float | int | None = None
    as_measured: bool = False

    @model_validator(mode="after")
    def _one_scaling(self) -> Self:
        chosen = [
            self.annual_kwh is not None,
            self.peak_kwp is not None or self.yield_kwh_per_kwp is not None,
            self.as_measured,
        ]
        pv_pair = (self.peak_kwp is None) == (self.yield_kwh_per_kwp is None)
        if sum(chosen) != 1 or not pv_pair:
            msg = "give exactly one of annual_kwh, peak_kwp + yield_kwh_per_kwp, as_measured"
            raise ValueError(msg)
        return self

    def spec(self) -> Shaped:
        scaling: Scaling = AsMeasured()
        if self.annual_kwh is not None:
            scaling = Nominal(annual_kwh=float(self.annual_kwh))
        elif self.peak_kwp is not None and self.yield_kwh_per_kwp is not None:
            scaling = PVSystem(
                peak_kwp=float(self.peak_kwp),
                specific_yield_kwh_per_kwp=float(self.yield_kwh_per_kwp),
            )
        ref = ProfileRef(
            source=self.source, key=self.key, time_shift=timedelta(minutes=self.time_shift_minutes)
        )
        return Shaped(ref=ref, scaling=scaling)


class _Contract(_Strict):
    subscribed_kva: float | int
    off_peak: str = ""
    seasonal_off_peak: dict[str, str] = Field(default_factory=dict[str, str])
    fields: dict[str, str] = Field(default_factory=dict[str, str])
    supply_schedule: str | None = None


class _Asset(_Strict):
    id: str
    kind: str
    profile: _Profile | None = None
    options: dict[str, str] = Field(default_factory=dict[str, str])


class _Share(_Strict):
    direction: Literal["in", "out"]
    counterparty: str
    profile: _Profile


class _Site(_Strict):
    pack: str
    contract: _Contract
    assets: list[_Asset] = Field(default_factory=list[_Asset])
    shares: list[_Share] = Field(default_factory=list[_Share])


class _File(_Strict):
    sites: dict[str, _Site] = Field(min_length=1)


def _site(name: str, raw: _Site, packs: PackSource) -> SiteSpec:
    pack = packs.pack(raw.pack)
    supply = None
    if raw.contract.supply_schedule is not None:
        schedules = packs.schedules(raw.pack)
        if raw.contract.supply_schedule not in schedules:
            known = ", ".join(sorted(schedules)) or "none"
            msg = f"pack {raw.pack!r} has no schedule {raw.contract.supply_schedule!r} ({known})"
            raise DomainError(msg)
        supply = schedules[raw.contract.supply_schedule]
    contract = pack.contract(
        subscribed_kva=Decimal(str(raw.contract.subscribed_kva)),
        fields=raw.contract.fields,
        off_peak=TimeWindows.parse(raw.contract.off_peak),
        seasonal_off_peak={
            k: TimeWindows.parse(v) for k, v in raw.contract.seasonal_off_peak.items()
        },
        supply=supply,
    )
    return SiteSpec(
        id=name,
        contract=contract,
        assets=tuple(
            AssetSpec(
                id=asset.id,
                kind=asset.kind,
                profile=None if asset.profile is None else asset.profile.spec(),
                options=tuple(sorted(asset.options.items())),
            )
            for asset in raw.assets
        ),
        shares=tuple(
            ShareSpec(
                direction=ShareDirection(share.direction),
                counterparty=share.counterparty,
                profile=share.profile.spec(),
            )
            for share in raw.shares
        ),
    )


def load_sites(text: str, packs: PackSource, *, origin: str = "<text>") -> dict[str, SiteSpec]:
    """Every site described in ``text``, by id; contracts are checked against their packs.

    Raises:
        DataFormatError: invalid TOML, an unknown field, an unknown pack or schedule, or a site
            that breaks a rule (a pack check of level ``error`` included).

    Warns:
        TariffWarning: a pack check of level ``warning``.
    """
    try:
        parsed = _File.model_validate(tomllib.loads(text))
    except tomllib.TOMLDecodeError as error:
        msg = f"{origin}: not valid TOML: {error}"
        raise DataFormatError(msg) from None
    except ValidationError as error:
        msg = f"{origin}: {error}"
        raise DataFormatError(msg) from None
    sites: dict[str, SiteSpec] = {}
    for name, raw in parsed.sites.items():
        try:
            sites[name] = _site(name, raw, packs)
        except DomainError as error:
            msg = f"{origin} [{name}]: {error}"
            raise DataFormatError(msg) from None
    return sites


def read_sites(path: Path, packs: PackSource, *, max_bytes: int = MAX_BYTES) -> dict[str, SiteSpec]:
    """Every site in the TOML file at ``path``, by id.

    Raises:
        DataFormatError: the file is too large, not UTF-8, or malformed (see ``load_sites``).
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
    return load_sites(text, packs, origin=path.name)
