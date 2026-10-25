"""The composition root wires installed plugins, settings and the resolver (MEO-DI-1, MEO-PLG-4)."""

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from myenergy.adapters.sites.toml_files import load_sites, read_sites
from myenergy.bootstrap import asset_kind_plugins, make_app_container, profile_source_plugins
from myenergy.bootstrap.registry import Registry
from myenergy.bootstrap.settings import Settings
from myenergy.domain.flows import FlowKind
from myenergy.domain.packs import tagged
from myenergy.domain.profiles import (
    Nominal,
    ProfileKind,
    ProfileMeta,
    ProfileRef,
    Shaped,
    TimestampLabel,
)
from myenergy.domain.rates import RateKey
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.sites import AssetRole, AssetSpec
from myenergy.domain.time import TimeGrid
from myenergy.engine.profiles import ProfileResolver
from myenergy.engine.sites import SiteResolver
from myenergy.ports.assets import PowerProfiles
from myenergy.ports.packs import PackSource
from myenergy.ports.plugins import ProfileSourcePlugin
from myenergy.ports.profiles import ProfileSource

FIXTURES = Path(__file__).parents[1] / "fixtures" / "enedis"
DAY = TimeGrid(
    start=datetime(2024, 10, 1, tzinfo=UTC),
    end=datetime(2024, 10, 2, tzinfo=UTC),
    step=timedelta(minutes=15),
)


def settings(pack_roots: list[Path] | None = None, **sources: dict[str, str]) -> Settings:
    return Settings(_env_file=None, sources=sources, pack_roots=pack_roots or [])  # pyright: ignore[reportCallIssue]  # pydantic-settings init option


def test_installed_plugins_build_the_configured_sources() -> None:
    container = make_app_container(settings(enedis={"root": str(FIXTURES)}))
    try:
        sources = container.get(Mapping[str, ProfileSource])
        assert sorted(sources) == ["enedis", "synthetic"]
        resolver = container.get(ProfileResolver)
        load = resolver.power(
            Shaped(
                ref=ProfileRef(source="enedis", key="RES1_BASE"), scaling=Nominal(annual_kwh=3500)
            ),
            DAY,
        )
        assert load.energy().total() > 0
        assert container.get(Settings).options("enedis") == {"root": str(FIXTURES)}
    finally:
        container.close()


def test_unconfigured_sources_are_left_out() -> None:
    container = make_app_container(settings(), profile_source_plugins())
    try:
        assert list(container.get(Mapping[str, ProfileSource])) == ["synthetic"]
    finally:
        container.close()


class _Flat:
    """A test-only source, written against the port only."""

    name = "flat"

    def catalog(self) -> Sequence[ProfileMeta]:
        return (
            ProfileMeta(
                key="one",
                kind=ProfileKind.CONSUMPTION,
                coverage=DAY,
                label=TimestampLabel.START,
                description="flat",
            ),
        )

    def shape(self, key: str, grid: TimeGrid) -> TimeSeries:
        assert key == "one"
        return TimeSeries.constant(grid, 1.0, Quantity.DIMENSIONLESS)


class FlatPlugin:
    """A test-only plugin: it joins the application without editing any module (MEO-PLG-4)."""

    name = "flat"

    def create(self, options: Mapping[str, str]) -> ProfileSource | None:
        return _Flat() if options.get("enabled") == "yes" else None


def test_a_new_plugin_joins_without_editing_code() -> None:
    plugins = Registry[ProfileSourcePlugin]("profile source")
    plugins.register("flat", FlatPlugin())
    container = make_app_container(settings(flat={"enabled": "yes"}), plugins)
    try:
        resolver = container.get(ProfileResolver)
        power = resolver.power(
            Shaped(ref=ProfileRef(source="flat", key="one"), scaling=Nominal(annual_kwh=8760)), DAY
        )
        assert power.values.tolist() == [1.0] * len(DAY)
    finally:
        container.close()


def test_built_in_packs_are_provided() -> None:
    container = make_app_container(settings())
    try:
        packs = container.get(PackSource)
        assert [pack.name for pack in packs.catalog()] == ["fr-household"]
        cta = packs.rates("fr-household").history(RateKey.of("cta", network="distribution"))
        assert cta.on(date(2026, 8, 1)).value == Decimal("0.15")
    finally:
        container.close()


def test_a_user_pack_joins_through_settings_without_code(tmp_path: Path) -> None:
    """MEO-PLG-4 for packs: a research pack is a folder named in the settings."""
    study = tmp_path / "flat-vat"
    (study / "rates").mkdir(parents=True)
    (study / "pack.toml").write_text(
        '[pack]\nname = "flat-vat"\ntitle = "t"\nextends = "fr-household"\n'
        'tags = { purpose = "research" }\n',
        encoding="utf-8",
    )
    (study / "rates" / "vat.toml").write_text(
        '[sources.s]\ntitle = "hypothesis"\nurl = "https://example.org"\n'
        '[[rates]]\ncomponent = "vat"\nselectors = { base = "consumption" }\nunit = "%"\n'
        '[[rates.versions]]\nfrom = 2024-08-01\nsource = "s"\nstatus = "to-verify"\nvalue = 0.0\n',
        encoding="utf-8",
    )
    container = make_app_container(settings(pack_roots=[tmp_path]))
    try:
        packs = container.get(PackSource)
        assert [pack.name for pack in tagged(packs.catalog(), purpose="research")] == ["flat-vat"]
        vat = packs.rates("flat-vat").history(RateKey.of("vat", base="consumption"))
        assert vat.on(date(2026, 1, 1), allow_to_verify=True).value == 0
    finally:
        container.close()


def test_sites_resolve_with_the_installed_asset_kinds() -> None:
    container = make_app_container(settings())
    try:
        sites = read_sites(
            Path(__file__).parents[1] / "fixtures" / "sites" / "street.toml",
            container.get(PackSource),
        )
        june = TimeGrid(
            start=datetime(2026, 6, 1, tzinfo=UTC),
            end=datetime(2026, 6, 2, tzinfo=UTC),
            step=timedelta(minutes=30),
        )
        flows = container.get(SiteResolver).flows(sites["sunny"], june)
        assert flows.totals()[FlowKind.EXPORT] > 0
        assert flows.totals()[FlowKind.SELF_CONSUMPTION] > 0
    finally:
        container.close()


class _Heater:
    """A test-only asset kind: a 1 kW heater, always on (MEO-PLG-4)."""

    name = "heater"
    role = AssetRole.SINK

    def power(self, asset: AssetSpec, grid: TimeGrid, profiles: PowerProfiles) -> TimeSeries:
        del asset, profiles  # always 1 kW
        return TimeSeries.constant(grid, 1.0, Quantity.POWER_KW)


def test_a_new_asset_kind_joins_without_editing_code() -> None:
    kinds = asset_kind_plugins()
    kinds.register("heater", _Heater())
    container = make_app_container(settings(), profile_source_plugins(), kinds)
    try:
        packs = container.get(PackSource)
        text = (
            '[sites.x]\npack = "fr-household"\n[sites.x.contract]\nsubscribed_kva = 6\n'
            'fields = { fta = "LU", supply_option = "base" }\n'
            '[[sites.x.assets]]\nid = "h"\nkind = "heater"\n'
        )
        site = load_sites(text, packs)["x"]
        flows = container.get(SiteResolver).flows(site, DAY)
        assert flows.totals()[FlowKind.IMPORT] == 24
    finally:
        container.close()
