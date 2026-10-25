"""Rate files are an input surface: size, encoding and schema are enforced (SEC-1, MEO-SEC-5)."""

from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.rates.toml_files import TomlRateSource

GOOD = """
[sources.doc]
title = "a document"
url = "https://example.org/doc.pdf"

[[rates]]
component = "cta"
unit = "%"

[[rates.versions]]
from = 2024-08-01
source = "doc"
status = "official"
value = 21.93
"""


def load(tmp_path: Path, content: str | bytes, max_bytes: int = 1024 * 1024) -> TomlRateSource:
    path = tmp_path / "rates.toml"
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return TomlRateSource([path], max_bytes=max_bytes)


def test_the_reference_file_loads(tmp_path: Path) -> None:
    assert len(load(tmp_path, GOOD).catalog()) == 1


def test_oversized_files_are_refused_before_parsing(tmp_path: Path) -> None:
    with pytest.raises(DataFormatError, match="more than the 100 allowed"):
        load(tmp_path, GOOD, max_bytes=100)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"\xff\xfe" + GOOD.encode("utf-16-le"), "not UTF-8"),
        ("[[rates]\n", "not valid TOML"),
        (GOOD.replace('unit = "%"', 'unit = "%"\nformula = "__import__(\'os\')"'), "Extra inputs"),
        (GOOD.replace('"%"', '"bananas"'), "unit"),
        (GOOD.replace("https://", "file:///"), "url"),
        (GOOD.replace("value = 21.93", 'value = "21.93"'), "value"),
        (GOOD.replace("from = 2024-08-01", 'from = "2024-08-01"'), "from"),
        (GOOD.replace('"official"', '"trust-me"'), "status"),
        (GOOD.replace('"cta"', '""'), "component"),
        ('[sources.doc]\ntitle = "t"\nurl = "https://x.org"\nrates = []\n', "rates"),
    ],
)
def test_malformed_files_are_refused(tmp_path: Path, content: str | bytes, message: str) -> None:
    with pytest.raises(DataFormatError, match=message):
        load(tmp_path, content)
