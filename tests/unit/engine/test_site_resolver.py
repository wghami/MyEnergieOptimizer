"""The site resolver turns assets into signed powers and flows, knowing kinds only by role."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.adapters.profiles.memory import InMemoryProfileSource
from myenergy.domain.contract import Contract
from myenergy.domain.errors import SiteError, TariffWarning
from myenergy.domain.flows import FlowKind
from myenergy.domain.profiles import (
    AsMeasured,
    ProfileKind,
    ProfileMeta,
    ProfileRef,
    ProfileUnit,
    Shaped,
    TimestampLabel,
)
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.sites import AssetRole, AssetSpec, ShareDirection, ShareSpec, SiteSpec
from myenergy.domain.time import TimeGrid
from myenergy.engine.assets import CONSUMER, PV
from myenergy.engine.profiles import ProfileResolver
from myenergy.engine.sites import SiteResolver
from myenergy.ports.assets import AssetKind, PowerProfiles

START = datetime(2026, 6, 1, 12, tzinfo=UTC)
HOUR = TimeGrid(start=START, end=START + timedelta(hours=1), step=timedelta(minutes=30))
VALUES = {"house": [2.0, 2.0], "roof": [3.0, 1.0], "op": [0.0, 0.5]}


def _measured() -> ProfileResolver:
    entries: dict[str, tuple[ProfileMeta, TimeSeries]] = {}
    for key, values in VALUES.items():
        meta = ProfileMeta(
            key=key,
            kind=ProfileKind.CONSUMPTION,
            coverage=HOUR,
            label=TimestampLabel.START,
            description=key,
            unit=ProfileUnit.KW,
        )
        entries[key] = (
            meta,
            TimeSeries(grid=HOUR, values=np.array(values), quantity=Quantity.DIMENSIONLESS),
        )
    return ProfileResolver({"m": InMemoryProfileSource("m", entries)})


def profile(key: str) -> Shaped:
    return Shaped(ref=ProfileRef(source="m", key=key), scaling=AsMeasured())


PACKS = TomlPackSource([builtin_packs()])
CONTRACT = Contract(pack="fr-household", subscribed_kva=Decimal(6))


def resolver(**extra: AssetKind) -> SiteResolver:
    return SiteResolver({"consumer": CONSUMER, "pv": PV, **extra}, _measured(), PACKS)


def site(*assets: AssetSpec, shares: tuple[ShareSpec, ...] = ()) -> SiteSpec:
    return SiteSpec(id="home", contract=CONTRACT, assets=assets, shares=shares)


HOUSE = AssetSpec(id="house", kind="consumer", profile=profile("house"))
ROOF = AssetSpec(id="roof", kind="pv", profile=profile("roof"))


def test_powers_are_signed_by_role() -> None:
    powers = resolver().powers(site(HOUSE, ROOF), HOUR)
    assert powers["house"].values.tolist() == [-2.0, -2.0]
    assert powers["roof"].values.tolist() == [3.0, 1.0]


def test_flows_with_a_share() -> None:
    share = ShareSpec(direction=ShareDirection.IN, counterparty="op", profile=profile("op"))
    with pytest.warns(
        TariffWarning,
        match="allocates shared energy every 0:30:00, but flows are computed every 0:15:00",
    ):
        resolver().flows(site(HOUSE, ROOF, shares=(share,)), HOUR.with_step(timedelta(minutes=15)))
    flows = resolver().flows(site(HOUSE, ROOF, shares=(share,)), HOUR)
    assert flows.imported.values.tolist() == [0.0, 0.5]
    assert flows.exported.values.tolist() == [0.5, 0.0]
    assert flows.flow(FlowKind.SUPPLIED).values.tolist() == [0.0, 0.25]
    assert flows.flow(FlowKind.SHARED_IN, "op").values.tolist() == [0.0, 0.25]


class _Storage:
    name = "storage"
    role = AssetRole.STORAGE

    def power(self, asset: AssetSpec, grid: TimeGrid, profiles: PowerProfiles) -> TimeSeries:
        del asset, profiles  # charges, then discharges, whatever the asset
        return TimeSeries(grid=grid, values=np.array([-1.0, 1.0]), quantity=Quantity.POWER_KW)


class _Broken:
    name = "broken"

    def __init__(
        self, role: AssetRole, values: list[float], quantity: Quantity = Quantity.POWER_KW
    ) -> None:
        self.role = role
        self._series = TimeSeries(grid=HOUR, values=np.array(values), quantity=quantity)

    def power(self, asset: AssetSpec, grid: TimeGrid, profiles: PowerProfiles) -> TimeSeries:
        del asset, grid, profiles  # returns its fixed series, right or wrong
        return self._series


def test_a_new_kind_joins_without_changing_the_resolver() -> None:
    battery = AssetSpec(id="battery", kind="storage")
    flows = resolver(storage=_Storage()).flows(site(HOUSE, ROOF, battery), HOUR)
    assert flows.exported.values.tolist() == [0.0, 0.0]
    assert flows.imported.values.tolist() == [0.0, 0.0]


@pytest.mark.parametrize(
    ("kinds", "message"),
    [
        ({}, r"no asset kind 'broken' \(kinds: consumer, pv\)"),
        ({"broken": _Broken(AssetRole.SINK, [1, -1])}, "a sink cannot have negative power"),
        (
            {"broken": _Broken(AssetRole.SOURCE, [1, 1], Quantity.ENERGY_KWH)},
            "returned kWh on another grid",
        ),
    ],
)
def test_misbehaving_kinds_are_site_errors(kinds: Mapping[str, AssetKind], message: str) -> None:
    with pytest.raises(SiteError, match=message):
        resolver(**kinds).powers(site(AssetSpec(id="x", kind="broken")), HOUR)
