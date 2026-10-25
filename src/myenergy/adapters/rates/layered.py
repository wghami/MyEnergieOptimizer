"""Rates in layers: a key found in an upper layer hides the whole history of the lower ones.

A pack that extends another puts its own rates on top: redefining a key (say ``vat`` for a tax
study) replaces that key's history; every other key is inherited.
"""

from collections.abc import Sequence

from myenergy.domain.errors import UnknownRateError
from myenergy.domain.rates import RateHistory, RateKey
from myenergy.ports.rates import RateSource


class LayeredRateSource:
    """``layers[0]`` on top; each key comes from the first layer that holds it."""

    def __init__(self, name: str, layers: Sequence[RateSource]) -> None:
        """Stack ``layers``, the first on top."""
        self.name = name
        self._owner: dict[RateKey, RateSource] = {}
        for layer in reversed(layers):
            for key in layer.catalog():
                self._owner[key] = layer

    def catalog(self) -> Sequence[RateKey]:
        """Every key of every layer, sorted by component then selectors."""
        return sorted(self._owner, key=lambda key: (key.component, key.selectors))

    def history(self, key: RateKey) -> RateHistory:
        """The history of ``key`` from the topmost layer that holds it.

        Raises:
            UnknownRateError: no layer holds ``key``.
        """
        layer = self._owner.get(key)
        if layer is None:
            msg = f"no rate {key} in {self.name}"
            raise UnknownRateError(msg)
        return layer.history(key)
