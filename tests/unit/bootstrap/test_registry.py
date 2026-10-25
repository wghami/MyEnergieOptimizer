"""Registries hold named plugins; entry points are checked before use (MEO-PLG-1, MEO-PLG-2)."""

from importlib.metadata import EntryPoint

import pytest

from myenergy.bootstrap.registry import Registry, RegistryError, load_entry_points
from myenergy.ports.plugins import (
    PROFILE_SOURCES_GROUP,
    RATE_SOURCES_GROUP,
    ProfileSourcePlugin,
    RateSourcePlugin,
)


def test_register_and_iterate() -> None:
    registry = Registry[int]("number")
    registry.register("one", 1)
    registry.register("two", 2)
    assert registry.names() == ("one", "two")
    assert list(registry) == [("one", 1), ("two", 2)]
    with pytest.raises(RegistryError, match="number 'one' is registered twice"):
        registry.register("one", 3)
    assert registry.get("two") == 2
    with pytest.raises(RegistryError, match=r"no number 'three' \(registered: one, two\)"):
        registry.get("three")
    with pytest.raises(RegistryError, match=r"\(registered: none\)"):
        Registry[int]("number").get("one")


def test_installed_built_ins_are_entry_points() -> None:
    registry = load_entry_points(PROFILE_SOURCES_GROUP, "profile source", ProfileSourcePlugin)
    assert set(registry.names()) >= {"enedis", "synthetic"}
    rates = load_entry_points(RATE_SOURCES_GROUP, "rate source", RateSourcePlugin)
    assert "toml" in rates.names()


def test_entry_points_are_sorted_and_checked() -> None:
    good = [
        EntryPoint(
            name="synthetic", value="myenergy.adapters.profiles.plugins:SYNTHETIC", group="g"
        ),
        EntryPoint(name="enedis", value="myenergy.adapters.profiles.plugins:ENEDIS", group="g"),
    ]
    assert load_entry_points("g", "source", ProfileSourcePlugin, good).names() == (
        "enedis",
        "synthetic",
    )
    bad = [EntryPoint(name="len", value="builtins:len", group="g")]
    with pytest.raises(
        RegistryError, match="entry point 'len' in 'g' is not a ProfileSourcePlugin"
    ):
        load_entry_points("g", "source", ProfileSourcePlugin, bad)
