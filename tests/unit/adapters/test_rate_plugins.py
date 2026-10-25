"""The built-in rate plugin serves the packaged tables, or a folder chosen in the settings."""

from pathlib import Path

import pytest

from myenergy.adapters.errors import AdapterError
from myenergy.adapters.rates.plugins import TOML
from myenergy.ports.plugins import RateSourcePlugin

FILE = """
[sources.doc]
title = "a document"
url = "https://example.org/doc.pdf"

[[rates]]
component = "cta"
unit = "%"

[[rates.versions]]
from = 2026-02-01
source = "doc"
status = "official"
value = 15.0
"""


def test_the_plugin_satisfies_the_port() -> None:
    assert isinstance(TOML, RateSourcePlugin)
    assert TOML.name == "toml"


def test_packaged_tables_by_default() -> None:
    source = TOML.create({})
    assert source.name == "toml"
    assert len(source.catalog()) == 56


def test_a_folder_replaces_the_packaged_tables(tmp_path: Path) -> None:
    (tmp_path / "cta.toml").write_text(FILE, encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    assert [str(key) for key in TOML.create({"root": str(tmp_path)}).catalog()] == ["cta[]"]


def test_a_missing_folder_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(AdapterError, match="does not exist"):
        TOML.create({"root": str(tmp_path / "nowhere")})
