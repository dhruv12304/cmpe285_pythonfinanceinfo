#!/usr/bin/env bash
# Run script for Python Finance Info (macOS / Linux).
#
#   ./run.sh                 interactive mode (enter symbols one at a time)
#   ./run.sh ADBE MSFT       look up these symbols once and exit
#   ./run.sh --test          run the unit tests (no internet needed)
#
# On first run it creates a virtual environment in .venv and installs
# requirements.txt. Later runs reuse it and only reinstall if
# requirements.txt changes.

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Error: python3 was not found. Install Python 3.9+ from https://www.python.org/downloads/" >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "Error: Python 3.9 or newer is required (found $("$PYTHON" --version 2>&1))." >&2
    exit 1
fi

# Unit tests use fakes only, so they run without installing anything.
if [[ "${1:-}" == "--test" ]]; then
    exec "$PYTHON" -m unittest discover -s tests -v
fi

VENV=".venv"
STAMP="$VENV/.requirements.installed"

if [[ ! -x "$VENV/bin/python" ]]; then
    echo "Creating virtual environment in $VENV ..."
    "$PYTHON" -m venv "$VENV"
fi

if [[ ! -f "$STAMP" ]] || ! cmp -s requirements.txt "$STAMP"; then
    echo "Installing dependencies ..."
    if "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r requirements.txt; then
        cp requirements.txt "$STAMP"
    elif "$VENV/bin/python" -c 'import yfinance' >/dev/null 2>&1; then
        echo "Warning: could not update dependencies (offline?). Using the installed versions." >&2
    else
        echo "Error: could not install dependencies. Check your internet connection and run ./run.sh again." >&2
        exit 1
    fi
fi

exec "$VENV/bin/python" main.py "$@"
