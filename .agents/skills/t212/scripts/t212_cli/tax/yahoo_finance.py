import datetime
from typing import Any, Optional

import yfinance as yf
from curl_cffi import requests as cffi_requests


def _get_session() -> cffi_requests.Session:
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
