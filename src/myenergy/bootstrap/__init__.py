"""Composition root: the only place that wires concrete adapters to ports (ADR 0002, MEO-DI-1).

``make_app_container()`` builds the APP-scoped container: settings, the configured profile
sources, the ``ProfileResolver``, the ``PackSource`` (built-in and user tariff packs) and the
``SiteResolver`` (with every installed asset kind). Tests pass their own ``Settings`` and plugin
registries instead of patching anything (DI-3).
"""

from collections.abc import Mapping

from dishka import (
    Container,
    Provider,
    Scope,
    make_container,
    provide,  # pyright: ignore[reportUnknownVariableType]  # dishka types provide() loosely
)

from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.bootstrap.registry import Registry, load_entry_points
from myenergy.bootstrap.settings import Settings
from myenergy.engine.profiles import ProfileResolver
from myenergy.engine.sites import SiteResolver
from myenergy.ports.assets import ASSET_KINDS_GROUP, AssetKind
from myenergy.ports.packs import PackSource
from myenergy.ports.plugins import PROFILE_SOURCES_GROUP, ProfileSourcePlugin
from myenergy.ports.profiles import ProfileSource


def profile_source_plugins() -> Registry[ProfileSourcePlugin]:
    """Every installed profile-source plugin (built-in or third-party)."""
    return load_entry_points(PROFILE_SOURCES_GROUP, "profile source", ProfileSourcePlugin)


def asset_kind_plugins() -> Registry[AssetKind]:
    """Every installed asset kind (built-in or third-party)."""
    return load_entry_points(ASSET_KINDS_GROUP, "asset kind", AssetKind)


class AppProvider(Provider):
    """APP scope: settings, profile sources and resolver, tariff packs, site resolver."""

    scope = Scope.APP

    def __init__(
        self,
        settings: Settings,
        plugins: Registry[ProfileSourcePlugin],
        asset_kinds: Registry[AssetKind],
    ) -> None:
        """Use these settings and these plugins."""
        super().__init__()
        self._settings = settings
        self._plugins = plugins
        self._asset_kinds = asset_kinds

    @provide
    def settings(self) -> Settings:
        """The application settings."""
        return self._settings

    @provide
    def profile_sources(self, settings: Settings) -> Mapping[str, ProfileSource]:
        """Every configured source, by name; plugins without configuration are left out."""
        sources: dict[str, ProfileSource] = {}
        for name, plugin in self._plugins:
            source = plugin.create(settings.options(name))
            if source is not None:
                sources[name] = source
        return sources

    @provide
    def profile_resolver(self, sources: Mapping[str, ProfileSource]) -> ProfileResolver:
        """The resolver over every configured source."""
        return ProfileResolver(sources)

    @provide
    def packs(self, settings: Settings) -> PackSource:
        """The built-in tariff packs and those in ``settings.pack_roots``.

        Raises:
            DataFormatError: a malformed pack, or two packs with one name.
        """
        return TomlPackSource([builtin_packs(), *settings.pack_roots])

    @provide
    def site_resolver(self, profiles: ProfileResolver, packs: PackSource) -> SiteResolver:
        """Sites resolved with every installed asset kind."""
        return SiteResolver(dict(self._asset_kinds), profiles, packs)


def make_app_container(
    settings: Settings | None = None,
    plugins: Registry[ProfileSourcePlugin] | None = None,
    asset_kinds: Registry[AssetKind] | None = None,
) -> Container:
    """The application container (call ``close()`` when done)."""
    return make_container(
        AppProvider(
            settings or Settings(),
            plugins or profile_source_plugins(),
            asset_kinds or asset_kind_plugins(),
        )
    )
