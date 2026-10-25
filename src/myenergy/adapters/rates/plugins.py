"""Plugins for the built-in rate sources, registered as entry points like any third party's."""

from collections.abc import Mapping
from pathlib import Path

from myenergy.adapters.errors import AdapterError
from myenergy.adapters.rates.toml_files import TomlRateSource, packaged_rate_files
from myenergy.ports.rates import RateSource


class TomlRatesPlugin:
    """Option: ``root``, a folder of ``*.toml`` rate files used instead of the packaged tables."""

    name = "toml"

    def create(self, options: Mapping[str, str]) -> RateSource:
        """The packaged tables, or the files in ``root`` when it is set.

        Raises:
            AdapterError: ``root`` is not a folder.
        """
        root = options.get("root")
        if not root:
            return TomlRateSource(packaged_rate_files(), name=self.name)
        folder = Path(root)
        if not folder.is_dir():
            msg = f"rate folder {folder} does not exist"
            raise AdapterError(msg)
        return TomlRateSource(sorted(folder.glob("*.toml")), name=self.name)


TOML = TomlRatesPlugin()
