import yfinance as yf
from typing import Optional
import datetime


def get_historical_price(ticker: str, date: datetime.date) -> Optional[float]:
    """Fetch the close price of a ticker on a specific date (for Vorabpauschale)."""
    # Fetch a small window around the date to handle weekends/holidays
    start_date = date - datetime.timedelta(days=2)
    end_date = date + datetime.timedelta(days=3)

    ticker_obj = yf.Ticker(ticker)
    hist = ticker_obj.history(
        start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d")
    )

    if hist.empty:
        return None

    # Get the closest date
    hist.index = hist.index.tz_localize(None)
    hist_prices = hist["Close"].to_dict()

    # Sort dates by distance from target date
    closest_date = min(hist_prices.keys(), key=lambda d: abs((d.date() - date).days))
    return float(hist_prices[closest_date])
