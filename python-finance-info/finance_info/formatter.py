"""Turn a Quote into the three output lines the assignment specifies.

Example:
    Mon Oct 10 17:23:48 PDT 2016
    Adobe Systems Incorporated (ADBE)
    109.24 +0.60 (+0.55%)
"""

from datetime import datetime
from typing import Optional

from .models import Quote

TIMESTAMP_FORMAT = "%a %b %d %H:%M:%S %Z %Y"


def format_timestamp(now: Optional[datetime] = None) -> str:
    """Local date and time with the time-zone abbreviation, like Unix `date`."""
    moment = (now or datetime.now()).astimezone()
    return moment.strftime(TIMESTAMP_FORMAT)


def _signed(value: float) -> str:
    """Two decimals with an explicit sign; a value that rounds to zero is +0.00."""
    rounded = round(value, 2)
    if rounded == 0:
        rounded = 0.0  # avoid printing "-0.00"
    return f"{rounded:+.2f}"


def format_quote(quote: Quote, now: Optional[datetime] = None) -> str:
    return "\n".join(
        [
            format_timestamp(now),
            f"{quote.company_name} ({quote.symbol})",
            f"{quote.price:.2f} {_signed(quote.change)} ({_signed(quote.percent_change)}%)",
        ]
    )
