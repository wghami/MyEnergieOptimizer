"""The ``RateSource`` port: where dated rates come from (ADR 0006).

Packaged TOML tables now; a database filled by the billing-data agent later. Callers only ask for
the history of a key, so the storage can change without touching the bill engine.
"""

from collections.abc import Sequence
from typing import Protocol

from myenergy.domain.rates import RateHistory, RateKey


class RateSource(Protocol):
    """A store of dated rates."""

    @property
    def name(self) -> str:
        """A short, unique name for messages and settings."""
        ...

    def catalog(self) -> Sequence[RateKey]:
        """Every key this source holds."""
        ...

    def history(self, key: RateKey) -> RateHistory:
        """Every version of ``key``.

        Raises:
            UnknownRateError: the source does not hold ``key``.
        """
        ...
