"""The built-in plugins build their sources from plain options."""

from pathlib import Path

import pytest

from myenergy.adapters.errors import AdapterError
from myenergy.adapters.profiles.enedis import EnedisParquetSource
from myenergy.adapters.profiles.plugins import ENEDIS, SYNTHETIC
from myenergy.adapters.profiles.synthetic import SyntheticProfileSource
from myenergy.ports.plugins import ProfileSourcePlugin

FIXTURES = Path(__file__).parents[2] / "fixtures" / "enedis"


def test_plugins_satisfy_the_port() -> None:
    assert isinstance(ENEDIS, ProfileSourcePlugin)
    assert isinstance(SYNTHETIC, ProfileSourcePlugin)
    assert (ENEDIS.name, SYNTHETIC.name) == ("enedis", "synthetic")


def test_enedis_is_off_without_a_folder() -> None:
    assert ENEDIS.create({}) is None
    assert ENEDIS.create({"root": ""}) is None


def test_enedis_reads_the_configured_folder_and_column() -> None:
    source = ENEDIS.create({"root": str(FIXTURES)})
    assert isinstance(source, EnedisParquetSource)
    assert "coefficient_ajuste" in source.catalog()[0].description
    other = ENEDIS.create({"root": str(FIXTURES), "column": "coefficient_prepare"})
    assert isinstance(other, EnedisParquetSource)
    assert "coefficient_prepare" not in source.catalog()[0].description
    assert other.name == "enedis"


def test_synthetic_options() -> None:
    default = SYNTHETIC.create({})
    assert isinstance(default, SyntheticProfileSource)
    tuned = SYNTHETIC.create({"seed": "7", "latitude": "43.6", "longitude": "1.44"})
    assert isinstance(tuned, SyntheticProfileSource)


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"seed": "seven"}, "option 'seed' must be int, got 'seven'"),
        ({"latitude": "north"}, "option 'latitude' must be float, got 'north'"),
    ],
)
def test_bad_options_are_reported(options: dict[str, str], message: str) -> None:
    with pytest.raises(AdapterError, match=message):
        SYNTHETIC.create(options)
