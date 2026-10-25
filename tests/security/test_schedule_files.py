"""Schedule files are an input surface: size, encoding and schema are enforced (SEC-1)."""

from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.tariffs.schedules import read_schedules
from myenergy.domain.schedules import Schedule

GOOD = """
[schedules.hp-hc]
default = "HP"

[[schedules.hp-hc.periods]]
name = "HC"
windows = "22:00-06:00"
"""


def read(tmp_path: Path, content: str | bytes, max_bytes: int = 256 * 1024) -> dict[str, Schedule]:
    path = tmp_path / "schedules.toml"
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return read_schedules(path, max_bytes=max_bytes)


def test_the_reference_file_loads(tmp_path: Path) -> None:
    assert list(read(tmp_path, GOOD)) == ["hp-hc"]


def test_oversized_files_are_refused(tmp_path: Path) -> None:
    with pytest.raises(DataFormatError, match="more than the 50 allowed"):
        read(tmp_path, GOOD, max_bytes=50)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"\xff\xfe" + GOOD.encode("utf-16-le"), "not UTF-8"),
        ("[schedules.x\n", "not valid TOML"),
        ("schedules = {}\n", "schedules"),
        (GOOD.replace('name = "HC"', 'name = "HC"\nexec = "rm -rf /"'), "Extra inputs"),
        (GOOD.replace('"22:00-06:00"', "2200"), "windows"),
        (GOOD.replace('default = "HP"', "default = 1"), "default"),
        (GOOD.replace('windows = "22:00-06:00"', 'days = "sat"'), "days"),
    ],
)
def test_malformed_files_are_refused(tmp_path: Path, content: str | bytes, message: str) -> None:
    with pytest.raises(DataFormatError, match=message):
        read(tmp_path, content)
