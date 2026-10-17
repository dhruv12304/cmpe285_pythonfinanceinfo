#!/usr/bin/env python3
"""Entry point: python main.py [SYMBOL ...]"""

import sys

if sys.version_info < (3, 9):
    sys.exit("Error: Python 3.9 or newer is required.")

from finance_info.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
