"""Unit tests. They use fake tickers/providers, so no internet is needed.

Run: python -m unittest discover -s tests -v   (or ./run.sh --test)
"""

import contextlib
import io
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_info import cli  # noqa: E402
from finance_info.errors import (  # noqa: E402
    DataUnavailableError,
    InvalidSymbolError,
    NetworkError,
    ProviderError,
    RateLimitError,
)
from finance_info.formatter import format_quote  # noqa: E402
from finance_info.models import Quote  # noqa: E402
from finance_info.providers import (  # noqa: E402
    YahooFinanceProvider,
    normalize_symbol,
    translate_exception,
)


# ---------------------------------------------------------------- fakes

class FakeTicker:
    def __init__(self, info=None, raise_exc=None, fast_info=None):
        self._info = info
        self._raise = raise_exc
        self.fast_info = fast_info or {}

    @property
    def info(self):
        if self._raise is not None:
            raise self._raise
        return self._info


class YFRateLimitError(Exception):
    """Same class name as yfinance's, which is what the translator checks."""


class CurlConnectionError(Exception):
    pass


def provider_returning(*tickers, retries=2):
    queue = list(tickers)
    calls = []

    def factory(symbol):
        calls.append(symbol)
        return queue.pop(0) if len(queue) > 1 else queue[0]

    sleeps = []
    provider = YahooFinanceProvider(retries=retries, ticker_factory=factory, sleep=sleeps.append)
    return provider, calls, sleeps


ADOBE_INFO = {
    "longName": "Adobe Inc.",
    "regularMarketPrice": 109.24,
    "regularMarketPreviousClose": 108.64,
}


# ---------------------------------------------------------------- tests

class SymbolValidationTests(unittest.TestCase):
    def test_normalizes_case_and_whitespace(self):
        self.assertEqual(normalize_symbol("  adbe "), "ADBE")

    def test_accepts_real_world_formats(self):
        for symbol in ["BRK-B", "RELIANCE.NS", "^GSPC", "EURUSD=X", "BTC-USD"]:
            self.assertEqual(normalize_symbol(symbol), symbol)

    def test_rejects_empty_and_malformed(self):
        for bad in ["", "   ", "AB CD", "$$$", "A" * 20, "-ABC"]:
            with self.assertRaises(InvalidSymbolError):
                normalize_symbol(bad)


class FormatterTests(unittest.TestCase):
    def setUp(self):
        self.when = datetime(2016, 10, 10, 17, 23, 48, tzinfo=timezone(timedelta(hours=-7), "PDT"))

    def test_matches_assignment_example(self):
        quote = Quote("ADBE", "Adobe Systems Incorporated", 109.24, 108.64)
        lines = format_quote(quote, self.when).splitlines()
        self.assertEqual(lines[1], "Adobe Systems Incorporated (ADBE)")
        self.assertEqual(lines[2], "109.24 +0.60 (+0.55%)")
        self.assertRegex(lines[0], r"^\w{3} \w{3} \d{2} \d{2}:\d{2}:\d{2} \S+ \d{4}$")

    def test_negative_change_has_minus_sign(self):
        quote = Quote("ADBE", "Adobe Inc.", 247.64, 248.15)
        self.assertEqual(format_quote(quote, self.when).splitlines()[2], "247.64 -0.51 (-0.21%)")

    def test_no_negative_zero(self):
        quote = Quote("X", "X Corp", 10.0, 10.00001)
        self.assertEqual(format_quote(quote, self.when).splitlines()[2], "10.00 +0.00 (+0.00%)")


class ProviderTests(unittest.TestCase):
    def test_valid_symbol(self):
        provider, _, _ = provider_returning(FakeTicker(ADOBE_INFO))
        quote = provider.get_quote("ADBE")
        self.assertEqual(quote.company_name, "Adobe Inc.")
        self.assertAlmostEqual(quote.change, 0.60, places=6)

    def test_unknown_symbol_returns_empty_info(self):
        provider, _, _ = provider_returning(FakeTicker({"trailingPegRatio": None}))
        with self.assertRaises(InvalidSymbolError):
            provider.get_quote("ZZZZZZ")

    def test_http_404_is_invalid_symbol(self):
        provider, calls, _ = provider_returning(FakeTicker(raise_exc=Exception("HTTP Error 404: Not Found")))
        with self.assertRaises(InvalidSymbolError):
            provider.get_quote("ZZZZZZ")
        self.assertEqual(len(calls), 1, "permanent errors must not be retried")

    def test_never_uses_previous_close_as_price(self):
        info = {"longName": "Halted Co", "regularMarketPreviousClose": 5.0}
        provider, _, _ = provider_returning(FakeTicker(info))
        with self.assertRaises(DataUnavailableError):
            provider.get_quote("HALT")

    def test_fast_info_fallback(self):
        info = {"longName": "Fallback Inc"}
        fast = {"last_price": 12.0, "previous_close": 10.0}
        provider, _, _ = provider_returning(FakeTicker(info, fast_info=fast))
        self.assertAlmostEqual(provider.get_quote("FB").percent_change, 20.0)

    def test_network_failure_is_retried_then_reported(self):
        exc = CurlConnectionError("Failed to perform, curl: (7) CONNECT tunnel failed, response 403")
        provider, calls, sleeps = provider_returning(FakeTicker(raise_exc=exc), retries=2)
        with self.assertRaises(NetworkError):
            provider.get_quote("ADBE")
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeps, [1.0, 2.0])  # exponential backoff

    def test_recovers_after_transient_failure(self):
        provider, _, _ = provider_returning(
            FakeTicker(raise_exc=OSError("Could not resolve host: query1.finance.yahoo.com")),
            FakeTicker(ADOBE_INFO),
        )
        self.assertEqual(provider.get_quote("ADBE").symbol, "ADBE")

    def test_rate_limit(self):
        provider, _, _ = provider_returning(FakeTicker(raise_exc=YFRateLimitError("Too Many Requests")), retries=0)
        with self.assertRaises(RateLimitError):
            provider.get_quote("ADBE")


class TranslateExceptionTests(unittest.TestCase):
    def test_builtin_connection_error(self):
        self.assertIsInstance(translate_exception(ConnectionError("x"), "A"), NetworkError)

    def test_timeout(self):
        self.assertIsInstance(translate_exception(TimeoutError("read timed out"), "A"), NetworkError)

    def test_wrapped_cause_is_inspected(self):
        try:
            try:
                raise ConnectionError("reset")
            except ConnectionError as inner:
                raise ValueError("wrapper") from inner
        except ValueError as outer:
            self.assertIsInstance(translate_exception(outer, "A"), NetworkError)

    def test_unknown_error(self):
        self.assertIsInstance(translate_exception(KeyError("weird"), "A"), ProviderError)


class FakeProvider:
    def __init__(self):
        self.asked = []

    def get_quote(self, symbol):
        self.asked.append(symbol)
        if symbol == "BAD":
            raise InvalidSymbolError("'BAD' is not a valid stock symbol.")
        if symbol == "BOOM":
            raise RuntimeError("unexpected")
        return Quote(symbol, "Adobe Inc.", 109.24, 108.64)


class CliTests(unittest.TestCase):
    def run_session(self, lines):
        feed = iter(lines)

        def read_line():
            try:
                return next(feed)
            except StopIteration:
                raise EOFError

        out, err, provider = io.StringIO(), io.StringIO(), FakeProvider()
        code = cli.interactive(provider, read_line, out, err)
        return code, out.getvalue(), err.getvalue(), provider

    def test_session_survives_errors_and_keeps_prompting(self):
        code, out, err, provider = self.run_session(["adbe", "BAD", "", "BOOM", "$$", "ADBE", "q"])
        self.assertEqual(code, 0)
        self.assertEqual(out.count(cli.PROMPT), 7)
        self.assertEqual(out.count("Adobe Inc. (ADBE)"), 2)
        self.assertIn("not a valid stock symbol", err)
        self.assertIn("No symbol entered", err)
        self.assertIn("Unexpected problem", err)
        self.assertIn("not a valid ticker symbol format", err)
        self.assertEqual(provider.asked, ["ADBE", "BAD", "BOOM", "ADBE"])  # '$$' never sent

    def test_end_of_input_exits_cleanly(self):
        code, _, _, _ = self.run_session([])
        self.assertEqual(code, 0)

    def test_one_shot_mode_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["ADBE"], provider=FakeProvider()), 0)
            self.assertEqual(cli.main(["ADBE", "BAD"], provider=FakeProvider()), 1)


if __name__ == "__main__":
    unittest.main()
