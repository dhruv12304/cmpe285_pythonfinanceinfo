"""Command-line interface.

Interactive (default):  python main.py
One-shot:               python main.py ADBE MSFT
"""

import argparse
import sys
from typing import Callable, List, Optional, TextIO

from . import __version__
from .errors import FinanceInfoError, SetupError
from .formatter import format_quote
from .providers import QuoteProvider, YahooFinanceProvider, normalize_symbol

PROMPT = "Please enter a symbol:"
QUIT_WORDS = {"q", "quit", "exit"}


def lookup(symbol_text: str, provider: QuoteProvider, out: TextIO, err: TextIO) -> bool:
    """Look up one symbol and print the result or a friendly error.

    Returns True on success. Expected failures are reported here, so one bad
    symbol leaves the session running.
    """
    try:
        symbol = normalize_symbol(symbol_text)
        quote = provider.get_quote(symbol)
    except FinanceInfoError as exc:
        print(f"Error: {exc}", file=err)
        return False
    except Exception as exc:  # last-resort guard: report and continue
        print(f"Error: Unexpected problem: {exc}", file=err)
        return False
    print(format_quote(quote), file=out)
    return True


def interactive(
    provider: QuoteProvider,
    read_line: Callable[[], str] = input,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> int:
    print("Python Finance Info - type a stock symbol (e.g. ADBE), or q to quit.\n", file=out)
    while True:
        print(PROMPT, file=out)
        out.flush()
        try:
            text = read_line()
        except (EOFError, KeyboardInterrupt):
            print(file=out)
            return 0
        if text.strip().lower() in QUIT_WORDS:
            return 0
        err.flush()
        lookup(text, provider, out, err)
        err.flush()
        print(file=out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python-finance-info",
        description="Show the current price and daily change for stock symbols.",
    )
    parser.add_argument(
        "symbols",
        nargs="*",
        help="ticker symbols to look up once (omit to start interactive mode)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="retries for network/rate-limit failures (default: 2)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Optional[List[str]] = None, provider: Optional[QuoteProvider] = None) -> int:
    args = build_parser().parse_args(argv)
    provider = provider or YahooFinanceProvider(retries=args.retries)

    try:
        if not args.symbols:
            return interactive(provider)
        ok = True
        for index, symbol in enumerate(args.symbols):
            if index:
                print()
            ok = lookup(symbol, provider, sys.stdout, sys.stderr) and ok
        return 0 if ok else 1
    except SetupError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
