"""Every ``AssetKind`` honours the same contract (PRT-1), including test-only ones (PRT-2)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from myenergy.adapters.profiles.synthetic import SyntheticProfileSource
from myenergy.domain.errors import SiteError
from myenergy.domain.profiles import Nominal, ProfileRef, Shaped
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.sites import AssetRole, AssetSpec
from myenergy.domain.time import TimeGrid
from myenergy.engine.assets import CONSUMER, PV
from myenergy.engine.profiles import ProfileResolver
from myenergy.ports.assets import AssetKind, PowerProfiles

START = datetime(2026, 6, 1, tzinfo=UTC)
DAY = TimeGrid(start=START, end=START + timedelta(days=1), step=timedelta(minutes=30))
PROFILES = ProfileResolver({"synthetic": SyntheticProfileSource()})
PROFILE = Shaped(
    ref=ProfileRef(source="synthetic", key="constant"), scaling=Nominal(annual_kwh=8760)
)


class CyclingBattery:
    """A test-only storage kind, written against the port only: +1 kW then -1 kW."""

    name = "cycling-battery"
    role = AssetRole.STORAGE

    def power(self, asset: AssetSpec, grid: TimeGrid, profiles: PowerProfiles) -> TimeSeries:
        del profiles  # this kind needs no profile
        if asset.options != (("kw", "1"),):
            raise SiteError(asset.id)
        values = np.where(np.arange(len(grid)) % 2 == 0, 1.0, -1.0)
        return TimeSeries(grid=grid, values=values, quantity=Quantity.POWER_KW)


KINDS: dict[str, Callable[[], tuple[AssetKind, AssetSpec]]] = {
    "consumer": lambda: (CONSUMER, AssetSpec(id="a", kind="consumer", profile=PROFILE)),
    "pv": lambda: (PV, AssetSpec(id="a", kind="pv", profile=PROFILE)),
    "cycling-battery": lambda: (
        CyclingBattery(),
        AssetSpec(id="a", kind="cycling-battery", options=(("kw", "1"),)),
    ),
}


@pytest.fixture(params=sorted(KINDS))
def kind_and_asset(request: pytest.FixtureRequest) -> tuple[AssetKind, AssetSpec]:
    return KINDS[request.param]()


def test_power_is_kw_on_the_requested_grid(kind_and_asset: tuple[AssetKind, AssetSpec]) -> None:
    kind, asset = kind_and_asset
    assert isinstance(kind, AssetKind)
    power = kind.power(asset, DAY, PROFILES)
    assert power.quantity is Quantity.POWER_KW
    assert power.grid == DAY
    if kind.role is not AssetRole.STORAGE:
        assert power.values.min() >= 0


def test_missing_requirements_are_site_errors(kind_and_asset: tuple[AssetKind, AssetSpec]) -> None:
    kind, asset = kind_and_asset
    with pytest.raises(SiteError):
        kind.power(AssetSpec(id="bare", kind=asset.kind, options=(("x", "y"),)), DAY, PROFILES)
