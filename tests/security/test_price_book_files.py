"""Price-book files are an input surface: size, encoding and schema are enforced (SEC-1)."""

from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.pricebooks.toml_files import LoadedBook, read_price_book

GOOD = """
[book]
name = "mine"

[[lines]]
name = "supply.energy"
basis = "per_kwh"
flow = "supplied"
rate = { component = "supply.energy" }
"""


def read(tmp_path: Path, content: str | bytes, max_bytes: int = 512 * 1024) -> LoadedBook:
    path = tmp_path / "book.toml"
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return read_price_book(path, max_bytes=max_bytes)


def test_the_reference_book_loads(tmp_path: Path) -> None:
    assert read(tmp_path, GOOD).book.name == "mine"


def test_oversized_files_are_refused(tmp_path: Path) -> None:
    with pytest.raises(DataFormatError, match="more than the 30 allowed"):
        read(tmp_path, GOOD, max_bytes=30)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"\xff\xfe" + GOOD.encode("utf-16-le"), "not UTF-8"),
        ("[book\n", "not valid TOML"),
        (GOOD.replace('name = "mine"', 'name = "../mine"'), "name"),
        (GOOD.replace('flow = "supplied"', 'flow = "teleported"'), "flow"),
        (GOOD + "formula = \"__import__('os')\"\n", "Extra inputs"),
        (GOOD.replace('basis = "per_kwh"', 'basis = "per_kwh"\ninclusion = "hidden"'), "inclusion"),
        (
            GOOD.replace(
                '[book]\nname = "mine"',
                '[book]\nname = "mine"\nsettings = { proration_days = "never" }',
            ),
            "proration_days",
        ),
        (GOOD + '[[rates]]\ncomponent = "x"\nunit = "EUR"\n', "versions"),
    ],
)
def test_malformed_books_are_refused(tmp_path: Path, content: str | bytes, message: str) -> None:
    with pytest.raises(DataFormatError, match=message):
        read(tmp_path, content)
