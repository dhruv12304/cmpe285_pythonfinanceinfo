"""Data providers that turn a ticker symbol into a Quote.

`QuoteProvider` is the interface the rest of the program depends on.
`YahooFinanceProvider` is an adapter around the `yfinance` library. Adding a
different source (Alpha Vantage, Finnhub, a licensed vendor feed) means writing
another class with a `get_quote` method; nothing else has to change.
"""

import contextlib
import io
import logging
import math
import re
import socket
import time
from typing import Any, Callable, Iterator, Mapping, Optional, Protocol

from .errors import (
    DataUnavailableError,
    FinanceInfoError,
    InvalidSymbolError,
    NetworkError,
    ProviderError,
    RateLimitError,
    SetupError,
)
from .models import Quote

# Letters, digits and the punctuation Yahoo uses in real tickers:
# BRK-B, RELIANCE.NS, ^GSPC (index), EURUSD=X (currency), BTC-USD.
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,14}$")


def normalize_symbol(raw: str) -> str:
    """Trim and upper-case a symbol, rejecting anything that cannot be a ticker.

    Checking the format locally avoids a pointless network call for input
    like "hello world" or "$$$".
    """
    symbol = (raw or "").strip().upper()
    if not symbol:
        raise InvalidSymbolError("No symbol entered.")
    if not _SYMBOL_PATTERN.match(symbol):
        raise InvalidSymbolError(f"'{symbol}' is not a valid ticker symbol format.")
    return symbol


class QuoteProvider(Protocol):
    """Anything that can look up a quote for a normalized symbol."""

    def get_quote(self, symbol: str) -> Quote:
        ...


# --------------------------------------------------------------------------
# Translating library exceptions into our own error types
# --------------------------------------------------------------------------

_NETWORK_CLASS_NAMES = {
    "ConnectionError",
    "ConnectTimeout",
    "ReadTimeout",
    "Timeout",
    "ProxyError",
    "SSLError",
    "DNSError",
    "CurlError",
}
_NETWORK_HINTS = (
    "connection",
    "connect tunnel",
    "timed out",
    "timeout",
    "could not resolve",
    "resolve host",
    "name resolution",
    "name or service not known",
    "network is unreachable",
    "no route to host",
    "failed to establish",
    "max retries",
    "curl: (5)",
    "curl: (6)",
    "curl: (7)",
    "curl: (28)",
    "curl: (35)",
    "curl: (56)",
)
_INVALID_HINTS = ("404", "not found", "possibly delisted", "no data found", "symbol may be delisted")


def _exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def translate_exception(exc: BaseException, symbol: str) -> FinanceInfoError:
    """Map an arbitrary library/network exception to a FinanceInfoError."""
    chain = list(_exception_chain(exc))

    for e in chain:
        name, msg = type(e).__name__, str(e).lower()
        if name == "YFRateLimitError" or "too many requests" in msg or "rate limit" in msg:
            return RateLimitError(
                "The data provider is rate-limiting requests. Wait a minute and try again."
            )

    for e in chain:
        name, msg = type(e).__name__, str(e).lower()
        if (
            isinstance(e, (ConnectionError, TimeoutError, socket.gaierror, socket.timeout))
            or name in _NETWORK_CLASS_NAMES
            or any(hint in msg for hint in _NETWORK_HINTS)
        ):
            return NetworkError(
                "Could not reach the stock data service. Check your internet connection and try again."
            )

    for e in chain:
        name, msg = type(e).__name__, str(e).lower()
        if name == "YFTickerMissingError" or any(hint in msg for hint in _INVALID_HINTS):
            return InvalidSymbolError(f"'{symbol}' is not a valid stock symbol.")

    return ProviderError(f"Unexpected problem retrieving data for '{symbol}': {exc}")


# --------------------------------------------------------------------------
# Yahoo Finance adapter
# --------------------------------------------------------------------------


def _number(value: Any) -> Optional[float]:
    """Return value as a finite float, or None if it is missing/garbage."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_number(info: Mapping[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        number = _number(info.get(key))
        if number is not None:
            return number
    return None


def _default_ticker_factory(symbol: str) -> Any:
    try:
        import yfinance  # imported lazily so tests and --help work without it
    except ImportError as exc:
        raise SetupError(
            "The 'yfinance' package is not installed. Run ./run.sh "
            "(or: pip install -r requirements.txt)."
        ) from exc
    return yfinance.Ticker(symbol)


@contextlib.contextmanager
def _quiet_library_output() -> Iterator[None]:
    """yfinance prints raw HTTP errors itself; keep the CLI output clean."""
    logger = logging.getLogger("yfinance")
    previous_level = logger.level
    logger.setLevel(logging.CRITICAL + 1)
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            yield
    finally:
        logger.setLevel(previous_level)


class YahooFinanceProvider:
    """Fetch quotes from Yahoo Finance through the yfinance library.

    Transient failures (network blips, rate limits) are retried with
    exponential backoff. Permanent failures (bad symbol) fail immediately.
    """

    name = "Yahoo Finance (via yfinance)"

    def __init__(
        self,
        retries: int = 2,
        backoff_seconds: float = 1.0,
        ticker_factory: Callable[[str], Any] = _default_ticker_factory,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._retries = max(0, retries)
        self._backoff = max(0.0, backoff_seconds)
        self._ticker_factory = ticker_factory
        self._sleep = sleep

    def get_quote(self, symbol: str) -> Quote:
        attempt = 0
        while True:
            try:
                return self._fetch_once(symbol)
            except (NetworkError, RateLimitError):
                if attempt >= self._retries:
                    raise
                self._sleep(self._backoff * (2 ** attempt))
                attempt += 1

    def _fetch_once(self, symbol: str) -> Quote:
        ticker = self._ticker_factory(symbol)
        try:
            with _quiet_library_output():
                info = ticker.info or {}
        except FinanceInfoError:
            raise
        except Exception as exc:  # library raises many unrelated types
            raise translate_exception(exc, symbol) from exc

        if not isinstance(info, Mapping):
            raise ProviderError(f"Unexpected response format for '{symbol}'.")

        name = info.get("longName") or info.get("shortName") or info.get("displayName")
        price = _first_number(info, "regularMarketPrice", "currentPrice")
        previous_close = _first_number(info, "regularMarketPreviousClose", "previousClose")

        if not name and price is None:
            # Yahoo answers unknown symbols with an empty/near-empty record.
            raise InvalidSymbolError(f"'{symbol}' is not a valid stock symbol.")

        if price is None or previous_close is None:
            price, previous_close = self._fill_from_fast_info(ticker, price, previous_close)

        if price is None or previous_close is None or previous_close == 0:
            raise DataUnavailableError(
                f"No current price data is available for '{symbol}' right now."
            )

        return Quote(
            symbol=symbol,
            company_name=str(name or symbol),
            price=price,
            previous_close=previous_close,
        )

    @staticmethod
    def _fill_from_fast_info(ticker: Any, price: Optional[float], previous_close: Optional[float]):
        """Second source inside yfinance for when `info` lacks price fields."""
        try:
            with _quiet_library_output():
                fast = ticker.fast_info
                if price is None:
                    price = _number(fast["last_price"])
                if previous_close is None:
                    previous_close = _number(fast["previous_close"])
        except Exception:
            pass  # fall through; caller reports DataUnavailableError
        return price, previous_close
