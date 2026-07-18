"""Pie & portfolio historical value reconstruction.

The Trading 212 API exposes only current snapshots — no historical portfolio
or pie value series. This module reconstructs daily value history by:

1. Reading current pie components (ticker, ISIN, owned quantity).
2. Resolving each ISIN to a Yahoo Finance symbol.
3. Fetching daily close-price history for each symbol.
4. Converting each series to a target currency (default EUR) using daily FX.
5. Multiplying price × quantity per component and summing to produce the
   aggregate daily pie value series.

Caveats:
    - Assumes quantities held are constant across the window (the API gives
      no historical holdings snapshot). Buys/sells/dividend-reinvestments
      within the period are NOT reflected.
    - Dividends are not added (price return, not total return).
    - For cash inside the pie, we use the current reported cash value
      constant across the window.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from curl_cffi import requests as cffi_requests

from t212_cli.client.base import Trading212Client
from t212_cli.tax.yahoo_finance import _get_session
from t212_cli.tax.yahoo_symbols import resolve_yahoo_symbol


@dataclass
class ComponentHistory:
    """Per-component daily history (in target currency)."""

    ticker: str
    isin: str
    yahoo_symbol: str
    name: str
    quantity: float
    fund_currency: str
    target_currency: str
    price_history: pd.Series  # close price in fund currency, indexed by date
    fx_history: pd.Series  # fund→target FX rate, indexed by date
    value_history: pd.Series = field(init=False)

    def __post_init__(self) -> None:
        # Convert fund-currency prices to target currency, then × quantity
        # FX convention: 1 unit of fund currency = fx_history units of target
        target_prices = self.price_history * self.fx_history
        self.value_history = (target_prices * self.quantity).round(4)


@dataclass
class PieHistory:
    """Aggregated pie value history."""

    pie_id: int
    pie_name: str
    target_currency: str
    cash: float
    components: list[ComponentHistory]
    aggregate_value: pd.Series = field(init=False)
    start_date: datetime.date = field(init=False)
    end_date: datetime.date = field(init=False)

    def __post_init__(self) -> None:
        if not self.components:
            empty = pd.Series(dtype=float)
            self.aggregate_value = empty
            self.start_date = datetime.date.today()
            self.end_date = datetime.date.today()
            return

        # Align all component value series on a common date index (forward
        # fill handles holidays where one exchange is closed but another is
        # open; leading NaNs are dropped so we start when all components
        # have their first price).
        frames = [c.value_history.rename(c.ticker) for c in self.components]
        aligned = pd.concat(frames, axis=1).ffill().dropna(how="all")
        # Cash contributes as a constant baseline
        aligned["_CASH"] = self.cash
        self.aggregate_value = aligned.sum(axis=1).round(2)
        idx = self.aggregate_value.index
        self.start_date = idx.min().date()
        self.end_date = idx.max().date()


def _fetch_fx(
    from_currency: str,
    to_currency: str,
    start: datetime.date,
    end: datetime.date,
    session: cffi_requests.Session | None = None,
) -> pd.Series:
    """Fetch daily FX rate series: 1 unit of `from` = N units of `to`.

    Uses yfinance's XXXYYY=X convention. Returns a Series of rates indexed
    by date. If from==to, returns a constant 1.0 series.

    GBp (pence) quirk: LSE-quoted ETFs are priced in pence (1 GBP = 100 GBp).
    Yahoo's `GBpEUR=X` actually returns the GBP→EUR rate (ignoring the "p"),
    so we must divide GBp rates by 100 after fetching.
    """
    if from_currency == to_currency:
        dates = pd.bdate_range(start, end)
        return pd.Series(1.0, index=dates, name="fx")

    pair = f"{from_currency}{to_currency}=X"
    yf_session = session if session is not None else _get_session()
    ticker = yf.Ticker(pair, session=yf_session)
    hist = ticker.history(start=start.isoformat(), end=end.isoformat())

    if hist.empty:
        # Fallback: assume flat rate of 1.0 (better than crashing)
        dates = pd.bdate_range(start, end)
        return pd.Series(1.0, index=dates, name="fx")

    rates = hist["Close"].copy()
    # GBp (pence) correction: Yahoo returns GBP rates even for GBpXXX=X pairs
    if from_currency == "GBp":
        rates = rates / 100.0

    rates.name = "fx"
    # yfinance returns tz-aware index; strip tz for clean date alignment
    if rates.index.tz is not None:
        rates.index = rates.index.tz_localize(None)
    return rates


def _fetch_price_history(
    yahoo_symbol: str,
    start: datetime.date,
    end: datetime.date,
    session: cffi_requests.Session,
) -> tuple[pd.Series, str]:
    """Fetch daily close prices and quote currency for a Yahoo symbol.

    Returns (prices, currency). Currency is sourced from yfinance's
    fast_info; falls back to "USD" if unavailable.
    """
    ticker = yf.Ticker(yahoo_symbol, session=session)
    hist = ticker.history(start=start.isoformat(), end=end.isoformat())
    # Detect quote currency (e.g. GBp, USD, EUR) from fast_info rather than
    # assuming based on exchange suffix.
    currency = "USD"
    try:
        currency = str(ticker.fast_info.get("currency", "USD"))
    except Exception:  # noqa: B110  # nosec B110
        pass
    if hist.empty:
        return pd.Series(dtype=float, name="price"), currency
    prices = hist["Close"].copy()
    prices.name = "price"
    # yfinance returns tz-aware index; strip tz for clean date alignment
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)
    return prices, currency


def fetch_pie_history(
    client: Trading212Client,
    pie_id: int,
    *,
    days: int = 30,
    target_currency: str = "EUR",
    session: Optional[cffi_requests.Session] = None,
) -> PieHistory:
    """Fetch and reconstruct daily value history for a pie.

    Args:
        client: Authenticated Trading212Client
        pie_id: Pie ID to analyze
        days: Number of calendar days of history (default 30)
        target_currency: Currency to normalize all values to (default EUR)
        session: Optional pre-configured curl_cffi session (for reuse /
            testing). A new session is created if None.

    Returns:
        PieHistory with per-component and aggregate daily value series.
    """
    sess = session if session is not None else _get_session()

    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)

    detail = client.get_pie_by_id(pie_id)
    pie_name = detail.settings.name if detail.settings else f"Pie {pie_id}"

    # Cash is not on the detailed response; fetch the summary list and find
    # this pie's cash by id.
    cash = 0.0
    try:
        for summary in client.get_pies():
            if summary.id == pie_id:
                cash = float(summary.cash or 0.0)
                break
    except Exception:  # noqa: B110  # nosec B110
        pass

    instruments = detail.instruments or []
    components: list[ComponentHistory] = []

    for inst in instruments:
        ticker = inst.ticker
        if not ticker:
            continue
        isin = client.resolve_isin_from_ticker(ticker) or ""
        quantity = float(inst.ownedQuantity or 0.0)
        if quantity <= 0 or not isin:
            continue

        symbol = resolve_yahoo_symbol(isin, session=sess)
        if not symbol:
            continue

        prices, fund_ccy = _fetch_price_history(symbol, start_date, end_date, sess)
        if prices.empty:
            continue

        fx = _fetch_fx(fund_ccy, target_currency, start_date, end_date, sess)
        # Reindex FX to match the price series dates (forward-fill)
        fx = fx.reindex(prices.index).ffill().bfill()

        components.append(
            ComponentHistory(
                ticker=ticker,
                isin=isin,
                yahoo_symbol=symbol,
                name=symbol,  # short name; enrichment optional
                quantity=quantity,
                fund_currency=fund_ccy,
                target_currency=target_currency,
                price_history=prices,
                fx_history=fx,
            )
        )

    return PieHistory(
        pie_id=pie_id,
        pie_name=pie_name or f"Pie {pie_id}",
        target_currency=target_currency,
        cash=cash,
        components=components,
    )


def summary_stats(series: pd.Series) -> dict[str, float]:
    """Compute summary statistics for a value series."""
    if series.empty:
        return {}
    clean = series.dropna()
    if clean.empty:
        return {}
    first = float(clean.iloc[0])
    last = float(clean.iloc[-1])
    return {
        "start_value": round(first, 2),
        "end_value": round(last, 2),
        "min_value": round(float(clean.min()), 2),
        "max_value": round(float(clean.max()), 2),
        "abs_change": round(last - first, 2),
        "pct_change": round((last - first) / first * 100, 2) if first else 0.0,
        "volatility_pct": (
            round(float(clean.pct_change().std() * np.sqrt(252) * 100), 2)
            if len(clean) > 1
            else 0.0
        ),
        "days": int(len(clean)),
    }
