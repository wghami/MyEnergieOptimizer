"""Settings come from the environment or a .env file; each source reads its own options."""

from pathlib import Path

import pytest

from myenergy.bootstrap.settings import Settings


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ENEDIS_DB_PATH",
        "MYENERGY_ENEDIS_DB_PATH",
        "MYENERGY_SOURCES__ENEDIS__ROOT",
        "MYENERGY_SOURCES__SYNTHETIC__SEED",
        "MYENERGY_PACK_ROOTS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]  # pydantic-settings init option
    assert settings.sources == {}
    assert settings.enedis_db_path is None
    assert settings.options("enedis") == {}
    assert settings.pack_roots == []


def test_pack_roots_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYENERGY_PACK_ROOTS", '["/data/packs", "/research/packs"]')
    assert Settings(_env_file=None).pack_roots == [Path("/data/packs"), Path("/research/packs")]  # pyright: ignore[reportCallIssue]  # pydantic-settings init option


def test_source_options_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYENERGY_SOURCES__SYNTHETIC__SEED", "7")
    monkeypatch.setenv("MYENERGY_SOURCES__ENEDIS__ROOT", "/data/enedis")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]  # pydantic-settings init option
    assert settings.options("synthetic") == {"seed": "7"}
    assert settings.options("enedis") == {"root": "/data/enedis"}
    assert settings.options("csv") == {}


@pytest.mark.parametrize("variable", ["ENEDIS_DB_PATH", "MYENERGY_ENEDIS_DB_PATH"])
def test_enedis_db_path_is_the_enedis_root(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.setenv(variable, "/legacy")
    assert Settings(_env_file=None).options("enedis") == {"root": "/legacy"}  # pyright: ignore[reportCallIssue]  # pydantic-settings init option


def test_an_explicit_root_wins_over_enedis_db_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENEDIS_DB_PATH", "/legacy")
    monkeypatch.setenv("MYENERGY_SOURCES__ENEDIS__ROOT", "/explicit")
    assert Settings(_env_file=None).options("enedis") == {"root": "/explicit"}  # pyright: ignore[reportCallIssue]  # pydantic-settings init option


def test_dot_env_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("MYENERGY_SOURCES__SYNTHETIC__LATITUDE=43.6\n")
    assert Settings(_env_file=env).options("synthetic") == {"latitude": "43.6"}  # pyright: ignore[reportCallIssue]  # pydantic-settings init option


def test_json_like_values_come_back_as_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYENERGY_SOURCES__SYNTHETIC__SEED", "7")
    monkeypatch.setenv("MYENERGY_SOURCES__SYNTHETIC__LATITUDE", "43.6")
    options = Settings(_env_file=None).options("synthetic")  # pyright: ignore[reportCallIssue]  # pydantic-settings init option
    assert options == {"seed": "7", "latitude": "43.6"}
