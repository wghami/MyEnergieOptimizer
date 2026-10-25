"""The network tariff's four time classes, as one built-in ``Schedule``.

TURPE prices energy by peak (HP) and off-peak (HC) hours of the high season (November to March)
and of the low season (April to October): HPH, HCH, HPB, HCB. Off-peak hours belong to each
connection and may differ between seasons.
"""

from collections.abc import Mapping
from enum import StrEnum

from myenergy.domain.schedules import PeriodRule, Schedule, Season, TimeWindows

HIGH_SEASON = "high"
LOW_SEASON = "low"
SEASON_DATES = {HIGH_SEASON: ((11, 1), (3, 31)), LOW_SEASON: ((4, 1), (10, 31))}
"""TURPE seasons: high from November to March, low from April to October."""
OFF_PEAK_HOURS_PER_DAY = 8.0
"""TURPE: a BT <= 36 kVA connection usually has 8 off-peak hours a day."""


class TimeClass(StrEnum):
    """The four TURPE time classes, in the order of the published grids."""

    HPH = "HPH"
    """Peak hours, high season."""
    HCH = "HCH"
    """Off-peak hours, high season."""
    HPB = "HPB"
    """Peak hours, low season."""
    HCB = "HCB"
    """Off-peak hours, low season."""


def network_schedule(
    off_peak: TimeWindows, low_season_off_peak: TimeWindows | None = None
) -> Schedule:
    """The TURPE schedule of a connection: its off-peak hours, per season if they differ."""
    return Schedule(
        name="turpe",
        rules=(
            PeriodRule(TimeClass.HCH.value, off_peak, seasons=frozenset({HIGH_SEASON})),
            PeriodRule(
                TimeClass.HCB.value,
                low_season_off_peak or off_peak,
                seasons=frozenset({LOW_SEASON}),
            ),
        ),
        seasons=turpe_seasons({HIGH_SEASON: TimeClass.HPH.value, LOW_SEASON: TimeClass.HPB.value}),
    )


def turpe_seasons(defaults: Mapping[str, str] | None = None) -> tuple[Season, Season]:
    """The two TURPE seasons, with an optional default period for each."""
    chosen = defaults or {}
    high, low = (
        Season(name, *SEASON_DATES[name], default=chosen.get(name))
        for name in (HIGH_SEASON, LOW_SEASON)
    )
    return high, low
