"""The package exposes the version that packaging derived from git tags (VER-1)."""

from importlib.metadata import version

import myenergy


def test_version_comes_from_the_installed_distribution() -> None:
    assert myenergy.__version__ == version("myenergyoptimizer")
