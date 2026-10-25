"""Composition root: the only place that wires concrete adapters to ports (ADR 0002, MEO-DI-1).

``make_app_container()`` builds the APP-scoped container: settings, the configured profile
sources, the ``ProfileResolver`` and the selected ``RateSource``. Tests pass their own ``Settings``
and plugin registries instead of patching anything (DI-3).
"""

from collections.abc import Mapping

from dishka import (
    Container,
    Provider,
    Scope,
    make_container,
    provide,  # pyright: ignore[reportUnknownVariableType]  # dishka types provide() loosely
)

from myenergy.bootstrap.registry import Registry, load_entry_points
from myenergy.bootstrap.settings import Settings
from myenergy.engine.profiles import ProfileResolver
from myenergy.ports.plugins import (
    PROFILE_SOURCES_GROUP,
    RATE_SOURCES_GROUP,
    ProfileSourcePlugin,
    RateSourcePlugin,
)
from myenergy.ports.profiles import ProfileSource
from myenergy.ports.rates import RateSource


def profile_source_plugins() -> Registry[ProfileSourcePlugin]:
    """Every installed profile-source plugin (built-in or third-party)."""
    return load_entry_points(PROFILE_SOURCES_GROUP, "profile source", ProfileSourcePlugin)


def rate_source_plugins() -> Registry[RateSourcePlugin]:
    """Every installed rate-source plugin (built-in or third-party)."""
    return load_entry_points(RATE_SOURCES_GROUP, "rate source", RateSourcePlugin)


class AppProvider(Provider):
    """APP scope: settings, profile sources, profile resolver, rate source."""

    scope = Scope.APP

    def __init__(
        self,
        settings: Settings,
        plugins: Registry[ProfileSourcePlugin],
        rate_plugins: Registry[RateSourcePlugin],
    ) -> None:
        """Use these settings and these plugins."""
        super().__init__()
        self._settings = settings
        self._plugins = plugins
        self._rate_plugins = rate_plugins

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
    def rate_source(self, settings: Settings) -> RateSource:
        """The rate source named by ``settings.rate_source``, built from its options.

        Raises:
            RegistryError: no rate-source plugin has that name.
        """
        name = settings.rate_source
        return self._rate_plugins.get(name).create(settings.options(name))


def make_app_container(
    settings: Settings | None = None,
    plugins: Registry[ProfileSourcePlugin] | None = None,
    rate_plugins: Registry[RateSourcePlugin] | None = None,
) -> Container:
    """The application container (call ``close()`` when done)."""
    return make_container(
        AppProvider(
            settings or Settings(),
            plugins or profile_source_plugins(),
            rate_plugins or rate_source_plugins(),
        )
    )
