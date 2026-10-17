"""Domain model: a stock quote, independent of where the data came from."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    """A snapshot of one stock's price against its previous close."""

    symbol: str
    company_name: str
    price: float
    previous_close: float

    @property
    def change(self) -> float:
        """Absolute change since the previous close (+ up, - down)."""
        return self.price - self.previous_close

    @property
    def percent_change(self) -> float:
        """Percentage change since the previous close (+ up, - down)."""
        return (self.change / self.previous_close) * 100.0
