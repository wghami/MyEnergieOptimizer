"""Developers' checkouts have the git hooks installed (HK-1); CI has no hooks to check."""

import os
import subprocess
import sys

import pytest


@pytest.mark.skipif("CI" in os.environ, reason="CI runs every hook stage itself (HK-5)")
def test_git_hooks_are_installed() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "project_standards", "check-hooks-installed"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
