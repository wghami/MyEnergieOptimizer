"""Typed errors of the adapters (PY-9)."""

from myenergy.domain.errors import MyEnergyError


class AdapterError(MyEnergyError):
    """An adapter could not read or reach its data."""


class DataFormatError(AdapterError):
    """Input data breaks its declared format: the message says where and how."""
