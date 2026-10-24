"""The package exposes the version that packaging derived from git tags (VER-1)."""

from importlib.metadata import version

import myenergie


def test_version_comes_from_the_installed_distribution() -> None:
    assert myenergie.__version__ == version("myenergieoptimizer")
