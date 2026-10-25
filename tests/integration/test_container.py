"""The composition root wires installed plugins, settings and the resolver (MEO-DI-1, MEO-PLG-4)."""

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from myenergy.bootstrap import make_app_container, profile_source_plugins
from myenergy.bootstrap.registry import Registry, RegistryError
from myenergy.bootstrap.settings import Settings
from myenergy.domain.errors import UnknownRateError
from myenergy.domain.profiles import (
    Nominal,
    ProfileKind,
    ProfileMeta,
    ProfileRef,
    Shaped,
    TimestampLabel,
)
from myenergy.domain.rates import RateHistory, RateKey, RateStatus, RateUnit, RateVersion
from myenergy.domain.series import Quantity, TimeSeries
from myenergy.domain.time import TimeGrid
from myenergy.engine.profiles import ProfileResolver
from myenergy.ports.plugins import ProfileSourcePlugin, RateSourcePlugin
from myenergy.ports.profiles import ProfileSource
from myenergy.ports.rates import RateSource

FIXTURES = Path(__file__).parents[1] / "fixtures" / "enedis"
DAY = TimeGrid(
    start=datetime(2024, 10, 1, tzinfo=UTC),
    end=datetime(2024, 10, 2, tzinfo=UTC),
    step=timedelta(minutes=15),
)


def settings(rate_source: str = "toml", **sources: dict[str, str]) -> Settings:
    return Settings(_env_file=None, sources=sources, rate_source=rate_source)  # pyright: ignore[reportCallIssue]  # pydantic-settings init option


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


def test_the_packaged_rate_tables_are_the_default_rate_source() -> None:
    container = make_app_container(settings())
    try:
        rates = container.get(RateSource)
        cta = rates.history(RateKey.of("cta", network="distribution"))
        assert cta.on(date(2026, 8, 1)).value == Decimal("0.15")
    finally:
        container.close()


class _FixedRates:
    """A test-only rate source, written against the port only."""

    name = "fixed"

    def __init__(self, vat: str) -> None:
        key = RateKey.of("vat", base="consumption")
        version = RateVersion(
            value=Decimal(vat),
            unit=RateUnit.FRACTION,
            valid_from=date(2020, 1, 1),
            valid_to=None,
            source="test",
            status=RateStatus.TO_VERIFY,
        )
        self._history = RateHistory(key, [version])

    def catalog(self) -> Sequence[RateKey]:
        return [self._history.key]

    def history(self, key: RateKey) -> RateHistory:
        if key != self._history.key:
            raise UnknownRateError(str(key))
        return self._history


class FixedRatesPlugin:
    """A test-only rate plugin (think: a database); it joins without editing code (MEO-PLG-4)."""

    name = "fixed"

    def create(self, options: Mapping[str, str]) -> RateSource:
        return _FixedRates(options.get("vat", "0.2"))


def test_a_new_rate_source_is_selected_by_settings() -> None:
    rate_plugins = Registry[RateSourcePlugin]("rate source")
    rate_plugins.register("fixed", FixedRatesPlugin())
    container = make_app_container(
        settings("fixed", fixed={"vat": "0.055"}), profile_source_plugins(), rate_plugins
    )
    try:
        history = container.get(RateSource).history(RateKey.of("vat", base="consumption"))
        assert history.on(date(2026, 1, 1), allow_to_verify=True).value == Decimal("0.055")
    finally:
        container.close()


def test_an_unknown_rate_source_is_an_error() -> None:
    container = make_app_container(settings("nowhere"))
    try:
        with pytest.raises(RegistryError, match="no rate source 'nowhere'"):
            container.get(RateSource)
    finally:
        container.close()
