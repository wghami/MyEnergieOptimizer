"""Application settings, from the environment or a git-ignored ``.env`` file (SEC-7).

Each profile source reads its own options, ``MYENERGY_SOURCES__<SOURCE>__<OPTION>``, for example
``MYENERGY_SOURCES__ENEDIS__ROOT=/data/enedis`` or ``MYENERGY_SOURCES__SYNTHETIC__SEED=7``.
``ENEDIS_DB_PATH`` is also accepted for the Enedis folder.
"""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every setting of the application."""

    model_config = SettingsConfigDict(
        env_prefix="MYENERGY_", env_nested_delimiter="__", env_file=".env", extra="ignore"
    )

    sources: dict[str, dict[str, str | int | float | bool]] = Field(default_factory=dict)
    """Environment values arrive parsed as JSON (``7`` is an int); ``options()`` returns text."""
    enedis_db_path: Path | None = Field(
        default=None, validation_alias=AliasChoices("MYENERGY_ENEDIS_DB_PATH", "ENEDIS_DB_PATH")
    )

    def options(self, source: str) -> dict[str, str]:
        """Options of one source (names are case-insensitive), with ``ENEDIS_DB_PATH`` folded in."""
        found = {
            key.lower(): str(value)
            for name, values in self.sources.items()
            if name.lower() == source
            for key, value in values.items()
        }
        if source == "enedis" and self.enedis_db_path is not None:
            found.setdefault("root", str(self.enedis_db_path))
        return found
