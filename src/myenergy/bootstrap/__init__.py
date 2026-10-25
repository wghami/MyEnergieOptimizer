"""Composition root: the only place that wires concrete adapters to ports (ADR 0002, MEO-DI-1).

``make_app_container()`` builds the APP-scoped container: settings, the configured profile sources
and the ``ProfileResolver``. Tests pass their own ``Settings`` and plugin registry instead of
patching anything (DI-3).
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
from myenergy.ports.plugins import PROFILE_SOURCES_GROUP, ProfileSourcePlugin
from myenergy.ports.profiles import ProfileSource


def profile_source_plugins() -> Registry[ProfileSourcePlugin]:
    """Every installed profile-source plugin (built-in or third-party)."""
    return load_entry_points(PROFILE_SOURCES_GROUP, "profile source", ProfileSourcePlugin)


class AppProvider(Provider):
    """APP scope: settings, profile sources, profile resolver."""

    scope = Scope.APP

    def __init__(self, settings: Settings, plugins: Registry[ProfileSourcePlugin]) -> None:
        """Use these settings and these plugins."""
        super().__init__()
        self._settings = settings
        self._plugins = plugins

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


def make_app_container(
    settings: Settings | None = None, plugins: Registry[ProfileSourcePlugin] | None = None
) -> Container:
    """The application container (call ``close()`` when done)."""
    return make_container(AppProvider(settings or Settings(), plugins or profile_source_plugins()))
