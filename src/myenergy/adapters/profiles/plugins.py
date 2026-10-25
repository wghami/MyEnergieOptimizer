"""Plugins for the built-in profile sources, registered as entry points like any third party's."""

from collections.abc import Mapping
from pathlib import Path

from myenergy.adapters.errors import AdapterError
from myenergy.adapters.profiles.enedis import EnedisParquetSource
from myenergy.adapters.profiles.synthetic import SyntheticProfileSource
from myenergy.ports.profiles import ProfileSource


def _number[T: (int, float)](options: Mapping[str, str], key: str, kind: type[T], default: T) -> T:
    raw = options.get(key)
    if raw is None:
        return default
    try:
        return kind(raw)
    except ValueError:
        msg = f"option {key!r} must be {kind.__name__}, got {raw!r}"
        raise AdapterError(msg) from None


class EnedisPlugin:
    """Options: ``root`` (the parquet folder; without it the source is off) and ``column``."""

    name = "enedis"

    def create(self, options: Mapping[str, str]) -> ProfileSource | None:
        """The Enedis source over ``root``, or ``None`` when no folder is configured."""
        root = options.get("root")
        if not root:
            return None
        return EnedisParquetSource(Path(root), column=options.get("column", "coefficient_ajuste"))


class SyntheticPlugin:
    """Options: ``seed`` (int), ``latitude`` and ``longitude`` (degrees). Always available."""

    name = "synthetic"

    def create(self, options: Mapping[str, str]) -> ProfileSource | None:
        """The synthetic source with the configured seed and PV location."""
        return SyntheticProfileSource(
            seed=_number(options, "seed", int, 0),
            latitude=_number(options, "latitude", float, 48.85),
            longitude=_number(options, "longitude", float, 2.35),
        )


ENEDIS = EnedisPlugin()
SYNTHETIC = SyntheticPlugin()
