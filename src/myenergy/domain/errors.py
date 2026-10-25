"""Typed errors of the domain (PY-9); every project error derives from ``MyEnergyError``."""


class MyEnergyError(Exception):
    """Root of every error raised by MyEnergyOptimizer."""


class DomainError(MyEnergyError):
    """A domain rule was violated."""


class GridError(DomainError):
    """A time grid is invalid, or a timestamp does not fit it."""


class SeriesError(DomainError):
    """Time series are incompatible, or a series holds invalid values."""


class CoverageError(DomainError):
    """A requested period lies outside the data that would have to cover it."""
