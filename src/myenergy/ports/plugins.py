"""Plugins: how a data source joins the application without editing it (MEO-PLG-1, MEO-PLG-2).

Built-in and third-party sources register the same way, through the ``myenergy.profile_sources``
entry-point group, each pointing at an object that satisfies ``ProfileSourcePlugin``.
"""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from myenergy.ports.profiles import ProfileSource

PROFILE_SOURCES_GROUP = "myenergy.profile_sources"


@runtime_checkable
class ProfileSourcePlugin(Protocol):
    """Builds one ``ProfileSource`` from plain text options (from settings)."""

    @property
    def name(self) -> str:
        """The source name, also the key of its options in the settings."""
        ...

    def create(self, options: Mapping[str, str]) -> ProfileSource | None:
        """The source, or ``None`` when it is not configured (e.g. no data folder given)."""
        ...
