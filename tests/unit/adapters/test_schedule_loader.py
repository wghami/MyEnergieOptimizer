"""Schedules written in TOML become domain schedules, with the file named in every error."""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.tariffs import schedules as module
from myenergy.adapters.tariffs.schedules import load_schedules, read_schedules
from myenergy.domain.schedules import Season, TimeWindows
from myenergy.domain.time import TimeGrid

EV = Path(__file__).parents[2] / "fixtures" / "schedules" / "ev-offer.toml"
PARIS = ZoneInfo("Europe/Paris")


def test_a_file_defines_named_schedules() -> None:
    ev = read_schedules(EV)["ev-offer"]
    assert ev.periods == ("super-off-peak", "off-peak", "summer-peak", "peak")
    assert ev.seasons == (
        Season.parse("winter", "11-01..03-31"),
        Season.parse("summer", "04-01..10-31", "summer-peak"),
    )
    assert ev.rules[1].windows == TimeWindows.parse("22:00-02:00 06:00-08:00")
    assert ev.rules[1].days == {"sat", "sun"}
    assert ev.rules[0].days is None
    saturday = datetime(2026, 1, 10, tzinfo=PARIS)
    weights = ev.weights(
        TimeGrid(start=saturday, end=saturday + timedelta(days=1), step=timedelta(hours=1))
    )
    hours = [weights.periods[int(i)] for i in weights.shares.argmax(axis=1)]
    assert hours[:8] == ["off-peak"] * 2 + ["super-off-peak"] * 4 + ["off-peak"] * 2
    assert hours[8:22] == ["peak"] * 14


def test_the_module_example_is_valid() -> None:
    assert module.__doc__ is not None
    example = module.__doc__.split("::")[1].split("Anything")[0].replace("\n    ", "\n")
    assert list(load_schedules(example)) == ["ev-offer"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[schedules.x]\ndefault = 'p'\nseasons = { a = '01-01' }\n", "MM-DD"),
        (
            "[schedules.x]\ndefault = 'p'\n[[schedules.x.periods]]\nname = 'q'\nwindows = 'noon'\n",
            "cannot read",
        ),
        (
            "[schedules.x]\n[[schedules.x.periods]]\nname = 'q'\nseasons = ['winter']\n",
            "unknown seasons",
        ),
    ],
)
def test_broken_schedules_name_the_origin(text: str, message: str) -> None:
    with pytest.raises(DataFormatError, match=rf"^mine\.toml \[x\]: .*{message}"):
        load_schedules(text, origin="mine.toml")
