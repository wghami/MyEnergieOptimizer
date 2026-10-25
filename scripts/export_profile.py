"""Export a load or production profile as kW on any grid, to check it outside the code.

For: anyone who wants to look at a profile in a spreadsheet or plot it elsewhere.

    uv run python -m scripts.export_profile --source synthetic --key household
        --annual-kwh 3500 --start 2026-01-01T00:00+01:00 --end 2026-01-08T00:00+01:00
        --out week.csv
"""

import argparse
import csv
import os
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from myenergy.adapters.profiles.csv_files import CsvProfile, CsvProfileSource, CsvUnit
from myenergy.adapters.profiles.enedis import EnedisParquetSource
from myenergy.adapters.profiles.synthetic import SyntheticProfileSource
from myenergy.domain.errors import MyEnergyError
from myenergy.domain.profiles import (
    AsMeasured,
    Calibrated,
    Nominal,
    ProfileKind,
    ProfileRef,
    PVSystem,
    Scaling,
    Shaped,
)
from myenergy.domain.time import TimeGrid
from myenergy.engine.profiles import ProfileResolver
from myenergy.ports.profiles import ProfileSource

DESCRIPTION = "Export a load or production profile as kW on any grid."


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--source", choices=["enedis", "synthetic", "csv"], required=True)
    parser.add_argument("--key", help="profile key in the source (not needed for --source csv)")
    parser.add_argument("--enedis-root", type=Path, help="Enedis folder (default: $ENEDIS_DB_PATH)")
    parser.add_argument("--csv", type=Path, help="CSV file with timestamp,value")
    parser.add_argument("--csv-unit", choices=[u.value for u in CsvUnit], default=CsvUnit.KW.value)
    scaling = parser.add_mutually_exclusive_group(required=True)
    scaling.add_argument("--annual-kwh", type=float, help="Nominal: annual energy")
    scaling.add_argument("--pv", type=float, nargs=2, metavar=("KWP", "YIELD"), help="PVSystem")
    scaling.add_argument("--calibrate", nargs=3, metavar=("KWH", "START", "END"), help="Calibrated")
    scaling.add_argument("--as-measured", action="store_true", help="the source holds kW already")
    parser.add_argument(
        "--start", type=datetime.fromisoformat, required=True, help="ISO, with offset"
    )
    parser.add_argument(
        "--end", type=datetime.fromisoformat, required=True, help="ISO, with offset"
    )
    parser.add_argument("--step", type=int, default=15, help="minutes (5, 10, 15, 20, 30, 60)")
    parser.add_argument("--out", type=Path, help="output CSV (default: standard output)")
    return parser


def _source(args: argparse.Namespace) -> tuple[ProfileSource, str]:
    if args.source == "synthetic":
        return SyntheticProfileSource(), args.key
    if args.source == "enedis":
        root = args.enedis_root or Path(
            os.environ.get("ENEDIS_DB_PATH", "ENEDIS_DB_PATH is not set")
        )
        return EnedisParquetSource(root), args.key
    profile = CsvProfile(
        key="csv", path=args.csv, kind=ProfileKind.CONSUMPTION, unit=CsvUnit(args.csv_unit)
    )
    return CsvProfileSource([profile]), "csv"


def _scaling(args: argparse.Namespace, step: timedelta) -> Scaling:
    if args.annual_kwh is not None:
        return Nominal(annual_kwh=args.annual_kwh)
    if args.pv is not None:
        return PVSystem(peak_kwp=args.pv[0], specific_yield_kwh_per_kwp=args.pv[1])
    if args.calibrate is not None:
        energy, start, end = args.calibrate
        window = TimeGrid(
            start=datetime.fromisoformat(start), end=datetime.fromisoformat(end), step=step
        )
        return Calibrated(energy_kwh=float(energy), window=window)
    return AsMeasured()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the export; return 0 on success and 2 on a domain or data error."""
    args = _parser().parse_args(argv)
    try:
        step = timedelta(minutes=args.step)
        grid = TimeGrid(start=args.start, end=args.end, step=step)
        source, key = _source(args)
        resolver = ProfileResolver({source.name: source})
        power = resolver.power(
            Shaped(ref=ProfileRef(source=source.name, key=key), scaling=_scaling(args, step)), grid
        )
    except (MyEnergyError, OSError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 2
    handle = args.out.open("w", newline="", encoding="utf-8") if args.out else sys.stdout
    writer = csv.writer(handle)
    writer.writerow(["timestamp", "power_kw"])
    writer.writerows(
        [moment.isoformat(), f"{value:.6f}"]
        for moment, value in zip(grid, power.values, strict=True)
    )
    if args.out:
        handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
