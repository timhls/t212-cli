import datetime
from typing import Any, Optional

import yfinance as yf
from curl_cffi import requests as cffi_requests


def _get_session() -> cffi_requests.Session:
    # nosec B501: SSL verification disabled as workaround for fc.yahoo.com SSL issues
    # See SKILL.md for full explanation of this workaround
    return cffi_requests.Session(verify=False, impersonate="chrome")


def get_ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol, session=_get_session())


def get_historical_price(ticker: str, date: datetime.date) -> Optional[float]:
    start_date = date - datetime.timedelta(days=2)
    end_date = date + datetime.timedelta(days=3)

    ticker_obj = get_ticker(ticker)
    hist = ticker_obj.history(
        start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d")
    )

    if hist.empty:
        return None

    hist.index = hist.index.tz_localize(None)
    hist_prices = hist["Close"].to_dict()
    closest_date = min(hist_prices.keys(), key=lambda d: abs((d.date() - date).days))
    return float(hist_prices[closest_date])


def get_quote_currency(ticker: str) -> Optional[str]:
    """Return the quote currency of a Yahoo symbol (e.g. 'EUR', 'USD', 'GBp')."""
    try:
        currency = get_ticker(ticker).fast_info.get("currency")
        return str(currency) if currency else None
    except Exception:  # nosec B110
        return None


def get_fx_rate_to_eur(currency: str, date: datetime.date) -> Optional[float]:
    """FX rate: 1 unit of `currency` = X EUR on `date`.

    GBp (pence) quirk: Yahoo's ``GBpEUR=X`` actually returns the GBP→EUR
    rate (ignoring the pence convention), so GBp rates must be divided
    by 100 after fetching.
    """
    if currency == "EUR":
        return 1.0
    from_currency = currency
    pence = False
    if currency in ("GBp", "GBX"):
        from_currency = "GBP"
        pence = True
    pair = f"{from_currency}EUR=X"
    hist = get_ticker(pair).history(
        start=(date - datetime.timedelta(days=4)).strftime("%Y-%m-%d"),
        end=(date + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    if hist.empty:
        return None
    rate = float(hist["Close"].iloc[-1])
    if pence:
        rate /= 100.0
    return rate


def get_historical_price_eur(ticker: str, date: datetime.date) -> Optional[float]:
    """Historical close price converted to EUR.

    Uses the symbol's quote currency (via fast_info) and converts with the
    historical FX rate. Falls back to the raw price if the currency cannot
    be determined (assumes EUR).
    """
    price = get_historical_price(ticker, date)
    if price is None:
        return None
    currency = get_quote_currency(ticker)
    if currency is None or currency == "EUR":
        return price
    fx = get_fx_rate_to_eur(currency, date)
    if fx is None:
        return None
    return price * fx


def get_etf_funds_data(ticker: str) -> Optional[dict[str, Any]]:
    try:
        t = get_ticker(ticker)
        fd = t.funds_data

        result: dict[str, Any] = {}

        th = fd.top_holdings
        if th is not None and not th.empty:
            holdings = []
            for symbol, row in th.iterrows():
                holdings.append(
                    {
                        "symbol": symbol,
                        "name": row.get("Name", ""),
                        "weight": float(row.get("Holding Percent", 0)),
                    }
                )
            result["holdings"] = holdings

        sw = fd.sector_weightings
        if sw:
            result["sector_weightings"] = {
                k.replace("_", " ").title(): float(v) for k, v in sw.items() if v
            }

        ac = fd.asset_classes
        if ac:
            result["asset_classes"] = {
                k.replace("Position", "").lower(): float(v) for k, v in ac.items() if v
            }

        fops = fd.fund_operations
        if fops is not None and not fops.empty:
            for idx, row in fops.iterrows():
                col = [c for c in fops.columns if c != "Category Average"]
                if col:
                    val = row.get(col[0])
                    result[str(idx).lower().replace(" ", "_")] = (
                        float(val) if val is not None and str(val) != "<NA>" else None
                    )

        return result if result else None

    except Exception:
        return None
