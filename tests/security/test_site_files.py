"""Site files are an input surface: size, encoding and schema are enforced (SEC-1, MEO-SEC-4)."""

from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.packs.toml_files import TomlPackSource, builtin_packs
from myenergy.adapters.sites.toml_files import read_sites
from myenergy.domain.sites import SiteSpec

PACKS = TomlPackSource([builtin_packs()])
GOOD = """
[sites.home]
pack = "fr-household"

[sites.home.contract]
subscribed_kva = 6
fields = { fta = "LU", supply_option = "base" }

[[sites.home.assets]]
id = "house"
kind = "consumer"
profile = { source = "synthetic", key = "household", annual_kwh = 3500 }
"""
SHARE = """
[[sites.home.shares]]
direction = "in"
counterparty = "x"
profile = { source = "s", key = "k", as_measured = true }
"""


def read(tmp_path: Path, content: str | bytes, max_bytes: int = 256 * 1024) -> dict[str, SiteSpec]:
    path = tmp_path / "sites.toml"
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return read_sites(path, PACKS, max_bytes=max_bytes)


def test_the_reference_file_loads(tmp_path: Path) -> None:
    assert list(read(tmp_path, GOOD)) == ["home"]


def test_oversized_files_are_refused(tmp_path: Path) -> None:
    with pytest.raises(DataFormatError, match="more than the 40 allowed"):
        read(tmp_path, GOOD, max_bytes=40)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"\xff\xfe" + GOOD.encode("utf-16-le"), "not UTF-8"),
        ("[sites.home\n", "not valid TOML"),
        ("sites = {}\n", "sites"),
        (
            GOOD.replace('kind = "consumer"', 'kind = "consumer"\npath = "/etc/passwd"'),
            "Extra inputs",
        ),
        (GOOD.replace("annual_kwh = 3500", "annual_kwh = 3500, as_measured = true"), "exactly one"),
        (GOOD.replace("annual_kwh = 3500", "peak_kwp = 3"), "exactly one"),
        (GOOD.replace("annual_kwh = 3500", 'annual_kwh = "3500"'), "annual_kwh"),
        (GOOD.replace('pack = "fr-household"', 'pack = "../../etc"'), "no tariff pack"),
        (GOOD + SHARE.replace('"in"', '"sideways"'), "direction"),
    ],
)
def test_malformed_files_are_refused(tmp_path: Path, content: str | bytes, message: str) -> None:
    with pytest.raises(DataFormatError, match=message):
        read(tmp_path, content)
