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


class UnknownProfileError(DomainError):
    """A profile reference names a source or a key that does not exist."""


class CalibrationError(DomainError):
    """A profile cannot be scaled as requested (e.g. a window with no energy)."""


class RateError(DomainError):
    """A rate is missing, ambiguous, unverified, or its history is inconsistent."""


class UnknownRateError(RateError):
    """No rate table has this component and these selectors."""


class UnverifiedRateError(RateError):
    """A ``to-verify`` rate was requested where only official rates are allowed."""


class ContractError(DomainError):
    """A supply contract breaks a tariff rule."""


class UnknownPackError(DomainError):
    """No tariff pack has this name."""


class ScheduleError(DomainError):
    """A time-of-use schedule is malformed, ambiguous, or leaves instants without a period."""


class TariffWarning(UserWarning):
    """A contract departs from the usual regulated values; it is still priced as given."""
