"""TOML rate files: units are converted exactly, versions merge across files, nothing is guessed."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from myenergy.adapters.errors import DataFormatError
from myenergy.adapters.rates.toml_files import TomlRateSource, packaged_rate_files
from myenergy.domain.errors import UnknownRateError
from myenergy.domain.rates import RateKey, RateStatus, RateUnit

SOURCE = """
[sources.doc]
title = "a test document"
url = "https://example.org/doc.pdf"
"""


def write(folder: Path, name: str, body: str, *, with_source: bool = True) -> Path:
    path = folder / name
    path.write_text((SOURCE if with_source else "") + body, encoding="utf-8")
    return path


def rate(component: str, unit: str, versions: str, extra: str = "") -> str:
    return f"""
[[rates]]
component = "{component}"
unit = "{unit}"
{extra}
{versions}
"""


def version(start: str, value: str, end: str | None = None, status: str = "official") -> str:
    until = f"to = {end}\n" if end else ""
    return f"""
[[rates.versions]]
from = {start}
{until}source = "doc"
status = "{status}"
value = {value}
"""


def test_published_units_become_canonical_units(tmp_path: Path) -> None:
    body = "".join(
        rate(f"r{index}", unit, version("2025-08-01", value))
        for index, (unit, value) in enumerate(
            [
                ("EUR/year", "16.80"),
                ("EUR/kVA/year", "10.11"),
                ("EUR/kWh", "0.25"),
                ("cEUR/kWh", "7.49"),
                ("EUR/MWh", "29.98"),
                ("%", "21.93"),
            ]
        )
    )
    source = TomlRateSource([write(tmp_path, "units.toml", body)])
    found = {key.component: source.history(key).on(date(2025, 8, 1)) for key in source.catalog()}
    assert [(found[f"r{i}"].value, found[f"r{i}"].unit) for i in range(6)] == [
        (Decimal("16.80"), RateUnit.EUR_PER_YEAR),
        (Decimal("10.11"), RateUnit.EUR_PER_KVA_YEAR),
        (Decimal("0.25"), RateUnit.EUR_PER_KWH),
        (Decimal("0.0749"), RateUnit.EUR_PER_KWH),
        (Decimal("0.02998"), RateUnit.EUR_PER_KWH),
        (Decimal("0.2193"), RateUnit.FRACTION),
    ]
    assert found["r0"].source == "a test document <https://example.org/doc.pdf>"


def test_by_expands_a_table_into_one_key_per_value(tmp_path: Path) -> None:
    body = rate(
        "turpe.withdrawal.energy",
        "cEUR/kWh",
        version("2025-08-01", "{ HPH = 7.49, HCB = 1.16 }"),
        'selectors = { fta = "CU4" }\nby = "time_class"',
    )
    source = TomlRateSource([write(tmp_path, "by.toml", body)])
    assert [str(key) for key in source.catalog()] == [
        "turpe.withdrawal.energy[fta=CU4, time_class=HCB]",
        "turpe.withdrawal.energy[fta=CU4, time_class=HPH]",
    ]


def test_versions_merge_across_files_and_end_where_the_next_begins(tmp_path: Path) -> None:
    first = write(tmp_path, "a.toml", rate("excise", "EUR/MWh", version("2025-02-01", "33.70")))
    second = write(
        tmp_path,
        "b.toml",
        rate("excise", "EUR/MWh", version("2025-08-01", "29.98", status="to-verify")),
    )
    history = TomlRateSource([second, first], name="mine").history(RateKey.of("excise"))
    assert [(v.valid_from, v.valid_to) for v in history] == [
        (date(2025, 2, 1), date(2025, 8, 1)),
        (date(2025, 8, 1), None),
    ]
    assert history.versions[1].status is RateStatus.TO_VERIFY


def test_an_explicit_end_is_kept(tmp_path: Path) -> None:
    path = write(tmp_path, "a.toml", rate("cta", "%", version("2024-08-01", "21.93", "2026-02-01")))
    history = TomlRateSource([path]).history(RateKey.of("cta"))
    assert history.versions[0].valid_to == date(2026, 2, 1)


def test_unknown_keys_name_what_is_known(tmp_path: Path) -> None:
    body = rate("vat", "%", version("2024-08-01", "20.0"), 'selectors = { base = "consumption" }')
    source = TomlRateSource([write(tmp_path, "vat.toml", body)])
    with pytest.raises(UnknownRateError, match=r"known for vat: vat\[base=consumption\]"):
        source.history(RateKey.of("vat", base="subscription"))
    with pytest.raises(UnknownRateError, match=r"^no rate cta\[\]$"):
        source.history(RateKey.of("cta"))


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (rate("x", "EUR/year", version("2025-08-01", "1.0").replace("doc", "nope")), "undeclared"),
        (rate("x", "EUR/year", version("2025-08-01", "{ a = 1.0 }")), "table exactly when"),
        (rate("x", "EUR/year", version("2025-08-01", "1.0"), 'by = "a"'), "table exactly when"),
        (
            rate(
                "x",
                "EUR/year",
                version("2025-08-01", "{ a = 1.0 }"),
                'selectors = { a = "b" }\nby = "a"',
            ),
            "already a selector",
        ),
        (rate("x", "EUR/year", version("2025-08-01", "1.0", "2025-08-01")), "empty validity"),
        (
            rate(
                "x",
                "EUR/year",
                version("2025-08-01", "1.0", "2026-01-01") + version("2025-09-01", "2.0"),
            ),
            "overlaps",
        ),
        (rate("x", "EUR/year", version("2025-08-01", "inf")), "finite number"),
    ],
)
def test_inconsistent_files_are_refused(tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(DataFormatError, match=message):
        TomlRateSource([write(tmp_path, "bad.toml", body)])


def test_overlaps_across_files_are_refused(tmp_path: Path) -> None:
    paths = [
        write(tmp_path, name, rate("x", "EUR/year", version("2025-08-01", value)))
        for name, value in (("a.toml", "1.0"), ("b.toml", "2.0"))
    ]
    with pytest.raises(
        DataFormatError, match=r"two versions start on 2025-08-01 \(a.toml, b.toml\)"
    ):
        TomlRateSource(paths)


def test_no_file_is_an_error() -> None:
    with pytest.raises(DataFormatError, match="no rate file"):
        TomlRateSource([])


def test_the_packaged_tables_load() -> None:
    names = sorted(path.name for path in packaged_rate_files())
    assert names == [
        "taxes.toml",
        "turpe6-2024-08-01.toml",
        "turpe6-2025-02-01.toml",
        "turpe7-2025-08-01.toml",
        "turpe7-2026-08-01.toml",
    ]
    assert len(TomlRateSource(packaged_rate_files()).catalog()) == 56
