"""Pack folders are an input surface: size, encoding, names and schema are enforced (SEC-1)."""

from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.packs.toml_files import TomlPackSource

GOOD = '[pack]\nname = "mine"\ntitle = "my pack"\n'


def load(tmp_path: Path, content: str | bytes, max_bytes: int = 256 * 1024) -> TomlPackSource:
    folder = tmp_path / "mine"
    folder.mkdir()
    path = folder / "pack.toml"
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return TomlPackSource([tmp_path], max_bytes=max_bytes)


def test_the_reference_pack_loads(tmp_path: Path) -> None:
    assert [pack.name for pack in load(tmp_path, GOOD).catalog()] == ["mine"]


def test_oversized_files_are_refused(tmp_path: Path) -> None:
    with pytest.raises(DataFormatError, match="more than the 20 allowed"):
        load(tmp_path, GOOD, max_bytes=20)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"\xff\xfe" + GOOD.encode("utf-16-le"), "not UTF-8"),
        ("[pack\n", "not valid TOML"),
        (GOOD.replace('"mine"', '"../../etc"'), "name"),
        (GOOD.replace('"mine"', '"Mine Pack"'), "name"),
        (GOOD + 'script = "import os"\n', "Extra inputs"),
        (GOOD + '[[checks]]\nmessage = "m"\nlevel = "fatal"\n', "level"),
        (GOOD + "[fields.f]\nvalues = []\n", "values"),
        (GOOD + '[supply]\nfield = "f"\noptions = {}\n', "options"),
        (GOOD.replace('title = "my pack"', "title = 3"), "title"),
    ],
)
def test_malformed_packs_are_refused(tmp_path: Path, content: str | bytes, message: str) -> None:
    with pytest.raises(DataFormatError, match=message):
        load(tmp_path, content)
