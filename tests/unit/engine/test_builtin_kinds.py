"""The built-in kinds read their asset's profile and take no options."""

from datetime import UTC, datetime, timedelta

import pytest

from myenergy.adapters.profiles.synthetic import SyntheticProfileSource
from myenergy.domain.errors import SiteError
from myenergy.domain.profiles import Nominal, ProfileRef, Shaped
from myenergy.domain.sites import AssetRole, AssetSpec
from myenergy.domain.time import TimeGrid
from myenergy.engine.assets import CONSUMER, PV
from myenergy.engine.profiles import ProfileResolver

START = datetime(2026, 1, 1, tzinfo=UTC)
DAY = TimeGrid(start=START, end=START + timedelta(days=1), step=timedelta(hours=1))
PROFILES = ProfileResolver({"synthetic": SyntheticProfileSource()})
FLAT = Shaped(ref=ProfileRef(source="synthetic", key="constant"), scaling=Nominal(annual_kwh=8760))


def test_roles_and_power() -> None:
    assert (CONSUMER.name, CONSUMER.role, PV.name, PV.role) == (
        "consumer",
        AssetRole.SINK,
        "pv",
        AssetRole.SOURCE,
    )
    power = CONSUMER.power(AssetSpec(id="a", kind="consumer", profile=FLAT), DAY, PROFILES)
    assert power.energy().total() == pytest.approx(24)


def test_options_are_refused() -> None:
    asset = AssetSpec(id="a", kind="pv", profile=FLAT, options=(("tilt", "30"),))
    with pytest.raises(SiteError, match=r"kind 'pv' takes no options, got \{'tilt': '30'\}"):
        PV.power(asset, DAY, PROFILES)
