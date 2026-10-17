"""Error types the rest of the program understands.

Every failure from the data provider is translated into one of these, so the
user interface only deals with these types and yfinance, curl and HTTP details
stay inside the provider.
"""


class FinanceInfoError(Exception):
    """Base class for all expected, user-reportable failures."""


class InvalidSymbolError(FinanceInfoError):
    """The symbol is malformed or the provider has no such ticker."""


class NetworkError(FinanceInfoError):
    """The provider could not be reached (offline, DNS, timeout, proxy...)."""


class RateLimitError(FinanceInfoError):
    """The provider refused the request because of too many calls."""


class DataUnavailableError(FinanceInfoError):
    """The ticker exists but the provider returned no usable price data."""


class ProviderError(FinanceInfoError):
    """Any other unexpected failure inside the data provider."""


class SetupError(FinanceInfoError):
    """A required dependency is missing from the environment."""
