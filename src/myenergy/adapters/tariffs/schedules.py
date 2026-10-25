"""User-defined time-of-use schedules from TOML.

One file may hold several schedules, each under ``[schedules.<name>]``::

    [schedules.ev-offer]
    default = "peak"                      # instants no period claims (optional)

    [schedules.ev-offer.seasons]          # optional; each date of the year in exactly one season
    winter = "11-01..03-31"
    summer = { dates = "04-01..10-31", default = "summer-peak" }

    [[schedules.ev-offer.periods]]
    name = "super-off-peak"
    windows = "02:00-06:00"               # as printed on a bill; leave out for the whole day

    [[schedules.ev-offer.periods]]
    name = "off-peak"
    windows = "22:00-02:00 06:00-08:00"
    days = ["sat", "sun"]                 # labels of the day calendar (optional)
    seasons = ["winter"]                  # declared seasons (optional)

Anything malformed or ambiguous is a ``DataFormatError`` naming the file and the schedule.
"""

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from myenergy.adapters.errors import DataFormatError
from myenergy.domain.errors import ScheduleError
from myenergy.domain.schedules import PeriodRule, Schedule, Season, TimeWindows

MAX_BYTES = 256 * 1024
"""Schedule files are small; larger inputs are refused (SEC-1)."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _Season(_Strict):
    dates: str
    default: str | None = None


class _Period(_Strict):
    name: str
    windows: str | None = None
    days: list[str] | None = None
    seasons: list[str] | None = None


class _Schedule(_Strict):
    default: str | None = None
    seasons: dict[str, str | _Season] = Field(default_factory=dict[str, str | _Season])
    periods: list[_Period] = Field(default_factory=list[_Period])


class _File(_Strict):
    schedules: dict[str, _Schedule] = Field(min_length=1)


def _season(name: str, raw: str | _Season) -> Season:
    if isinstance(raw, str):
        return Season.parse(name, raw)
    return Season.parse(name, raw.dates, raw.default)


def _rule(raw: _Period) -> PeriodRule:
    return PeriodRule(
        period=raw.name,
        windows=None if raw.windows is None else TimeWindows.parse(raw.windows),
        days=None if raw.days is None else frozenset(raw.days),
        seasons=None if raw.seasons is None else frozenset(raw.seasons),
    )


def load_schedules(text: str, *, origin: str = "<text>") -> dict[str, Schedule]:
    """Every schedule in ``text``, by name.

    Raises:
        DataFormatError: invalid TOML, an unknown field, or a schedule that breaks a rule.
    """
    try:
        parsed = _File.model_validate(tomllib.loads(text))
    except tomllib.TOMLDecodeError as error:
        msg = f"{origin}: not valid TOML: {error}"
        raise DataFormatError(msg) from None
    except ValidationError as error:
        msg = f"{origin}: {error}"
        raise DataFormatError(msg) from None
    schedules: dict[str, Schedule] = {}
    for name, raw in parsed.schedules.items():
        try:
            schedules[name] = Schedule(
                name=name,
                rules=tuple(_rule(period) for period in raw.periods),
                default=raw.default,
                seasons=tuple(_season(season, dates) for season, dates in raw.seasons.items()),
            )
        except ScheduleError as error:
            msg = f"{origin} [{name}]: {error}"
            raise DataFormatError(msg) from None
    return schedules


def read_schedules(path: Path, *, max_bytes: int = MAX_BYTES) -> dict[str, Schedule]:
    """Every schedule in the TOML file at ``path``, by name.

    Raises:
        DataFormatError: the file is too large, not UTF-8, or malformed (see ``load_schedules``).
    """
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        msg = f"{path.name}: {len(raw)} bytes, more than the {max_bytes} allowed"
        raise DataFormatError(msg)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        msg = f"{path.name}: not UTF-8: {error}"
        raise DataFormatError(msg) from None
    return load_schedules(text, origin=path.name)
