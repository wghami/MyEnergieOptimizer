"""The synthetic shapes are reproducible: these reference values must not change silently (SIM-7).

A deliberate change to the generator updates these numbers in the same commit, with the reason.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from myenergy.adapters.profiles.plugins import SYNTHETIC
from myenergy.adapters.profiles.synthetic import SyntheticProfileSource
from myenergy.domain.profiles import ProfileKind, TimestampLabel
from myenergy.domain.time import TimeGrid

DAY = TimeGrid(
    start=datetime(2026, 3, 15, tzinfo=UTC),
    end=datetime(2026, 3, 16, tzinfo=UTC),
    step=timedelta(hours=1),
)
HOUSEHOLD = [
    0.839514226126,
    0.823624980129,
    0.826688824947,
    0.845287881678,
    0.84127233484,
    1.253269836084,
    1.818737854741,
    1.299770159136,
    0.89406723518,
    0.845029293619,
    0.834860281282,
    0.832445240496,
    0.810124913826,
    0.901493882007,
    0.824300639041,
    0.856408350978,
    1.127560895206,
    2.039182930831,
    2.767081088335,
    2.068278236078,
    1.156417673211,
    0.883826594902,
    0.805302618922,
    0.794452497983,
]
PV = [
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.343257143111,
    1.10939223182,
    1.789519276794,
    2.335200736452,
    2.709314621834,
    2.886430127978,
    2.854541092214,
    2.615884613524,
    2.186789016581,
    1.596561492964,
    0.885491198773,
    0.157406585822,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
]


def test_reference_day_values() -> None:
    source = SyntheticProfileSource()
    assert np.allclose(source.shape("household", DAY).values, HOUSEHOLD, rtol=1e-9, atol=1e-12)
    assert np.allclose(source.shape("pv-clear-sky", DAY).values, PV, rtol=1e-9, atol=1e-12)
    assert np.allclose(source.shape("constant", DAY).values, 1.0, rtol=1e-12)


def test_defaults_are_seed_zero_in_paris() -> None:
    explicit = SyntheticProfileSource(seed=0, latitude=48.85, longitude=2.35)
    default = SyntheticProfileSource()
    for key in ("household", "pv-clear-sky"):
        assert np.array_equal(default.shape(key, DAY).values, explicit.shape(key, DAY).values)


def test_the_plugin_builds_the_same_source() -> None:
    plugin_default = SYNTHETIC.create({})
    assert plugin_default is not None
    tuned = SYNTHETIC.create({"seed": "7", "latitude": "43.6", "longitude": "1.44"})
    assert tuned is not None
    expected = SyntheticProfileSource(seed=7, latitude=43.6, longitude=1.44)
    for key in ("household", "pv-clear-sky"):
        assert np.array_equal(
            plugin_default.shape(key, DAY).values, SyntheticProfileSource().shape(key, DAY).values
        )
        assert np.array_equal(tuned.shape(key, DAY).values, expected.shape(key, DAY).values)


def test_catalog() -> None:
    catalog = {meta.key: meta for meta in SyntheticProfileSource().catalog()}
    assert {k: (m.kind, m.label, m.description) for k, m in catalog.items()} == {
        "household": (
            ProfileKind.CONSUMPTION,
            TimestampLabel.START,
            "morning and evening peaks, winter-heavy, with seeded noise",
        ),
        "pv-clear-sky": (
            ProfileKind.PRODUCTION,
            TimestampLabel.START,
            "clear-sky solar elevation at the configured location",
        ),
        "constant": (ProfileKind.CONSUMPTION, TimestampLabel.START, "flat 1.0"),
    }
