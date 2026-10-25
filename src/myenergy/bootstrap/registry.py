"""Typed registries filled from entry points (MEO-PLG-1, MEO-PLG-2)."""

from collections.abc import Iterable, Iterator
from importlib.metadata import EntryPoint, entry_points

from myenergy.domain.errors import MyEnergyError


class RegistryError(MyEnergyError):
    """A plugin is missing, duplicated, or not what its group expects."""


class Registry[T]:
    """Named plugins of one kind, in registration order."""

    def __init__(self, kind: str) -> None:
        """An empty registry for plugins of ``kind`` (used in messages)."""
        self._kind = kind
        self._items: dict[str, T] = {}

    def register(self, name: str, item: T) -> None:
        """Add ``item`` under ``name``.

        Raises:
            RegistryError: ``name`` is already registered.
        """
        if name in self._items:
            msg = f"{self._kind} {name!r} is registered twice"
            raise RegistryError(msg)
        self._items[name] = item

    def __iter__(self) -> Iterator[tuple[str, T]]:
        """``(name, item)`` pairs in registration order."""
        return iter(self._items.items())

    def names(self) -> tuple[str, ...]:
        """Every registered name."""
        return tuple(self._items)


def load_entry_points[T](
    group: str, kind: str, check: type[T], points: Iterable[EntryPoint] | None = None
) -> Registry[T]:
    """A registry with every plugin of the entry-point ``group``, checked to be a ``check``.

    ``points`` defaults to the installed entry points of ``group``.

    Raises:
        RegistryError: an entry point does not provide a ``check`` (runtime protocol check).
    """
    registry = Registry[T](kind)
    found = entry_points(group=group) if points is None else points
    for point in sorted(found, key=lambda p: p.name):
        plugin = point.load()
        if not isinstance(plugin, check):
            msg = f"entry point {point.name!r} in {group!r} is not a {check.__name__}"
            raise RegistryError(msg)
        registry.register(point.name, plugin)
    return registry
