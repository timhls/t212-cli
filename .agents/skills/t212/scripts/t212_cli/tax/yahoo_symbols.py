"""Resolve instrument ISINs to Yahoo Finance ticker symbols.

Yahoo Finance does not reliably support bare-ISIN lookups for European
UCITS ETFs/ETCs (fuzzy matching returns wrong prices). This module provides:

1. A curated static map of known ISIN → Yahoo symbol mappings (verified
   working as of 2026-07 against LSE/XETRA/AMS/PA/MI listings).
2. A fallback resolver that queries Yahoo's search API and picks the most
   liquid ETF/mutual-fund listing on a major European exchange.
3. Persistent override via the per-ISIN tax config (`yfinance_ticker` field),
   so users can pin a specific listing.
"""

from __future__ import annotations

from typing import Any, Optional

from curl_cffi import requests as cffi_requests

from t212_cli.tax.yahoo_finance import _get_session

# Exchange priority order (most liquid European ETF venues first).
# LSE listings tend to have the longest history and tightest spreads.
_PREFERRED_EXCHANGES = ("LSE", "GER", "AMS", "PAR", "MIL", "MUN", "DUS", "SWB")
_VALID_QUOTE_TYPES = ("ETF", "MUTUALFUND", "EQUITY")

# Curated, verified mappings. Add new funds here when discovered so future
# runs skip the search API entirely.
_KNOWN_SYMBOLS: dict[str, str] = {
    # iShares / BlackRock
    "IE00BP3QZB59": "IWFV.L",  # iShares Edge MSCI World Value Factor
    "IE00B4L5YC18": "IEMA.L",  # iShares MSCI EM
    "IE000RDRMSD1": "BLKC.AS",  # iShares Blockchain Technology
    # Xtrackers / DWS
    "IE00BM67HM91": "XDW0.L",  # Xtrackers MSCI World Energy
    "IE00BM67HS53": "XDWM.DE",  # Xtrackers MSCI World Materials
    "IE00BJ0KDQ92": "XDWD.L",  # Xtrackers MSCI World
    # HANetf
    "IE000OJ5TQP4": "ASWC.DE",  # HANetf Future of Defence
    # WisdomTree (commodity ETCs need specific exchange picks)
    "GB00B15KYB02": "AIGE.MI",  # WisdomTree Energy
    "GB00B15KYH63": "AIGAP.PA",  # WisdomTree Agriculture
    "IE0003BJ2JS4": "WNUC.DE",  # WisdomTree Uranium & Nuclear
}

# Currency of each known Yahoo symbol (ISO 4217). Used for FX normalization.
# GBp ( Pence ) is reported by Yahoo as "GBp" or "GBP"; we treat .L listings
# as GBp (i.e. 1/100 GBP) which is the convention for LSE-quoted ETFs.
_SYMBOL_CURRENCY: dict[str, str] = {
    "IWFV.L": "GBp",
    "IEMA.L": "GBp",
    "XDW0.L": "GBp",
    "XDWD.L": "GBp",
    "ASWC.DE": "EUR",
    "XDWM.DE": "EUR",
    "WNUC.DE": "EUR",
    "BLKC.AS": "EUR",
    "AIGE.MI": "EUR",
    "AIGAP.PA": "EUR",
}


def get_known_symbol(isin: str) -> Optional[str]:
    """Return a hardcoded, verified Yahoo symbol for an ISIN, if known."""
    return _KNOWN_SYMBOLS.get(isin)


def get_symbol_currency(symbol: str) -> str:
    """Return the ISO 4217 currency for a Yahoo symbol.

    Falls back to "USD" if unknown — caller should treat unknown as needing
    explicit FX lookup.
    """
    return _SYMBOL_CURRENCY.get(symbol, "USD")


def search_yahoo_symbol(
    isin: str, session: Optional[cffi_requests.Session] = None
) -> Optional[dict[str, str]]:
    """Query Yahoo Finance search API for an ISIN.

    Returns the best matching quote as a dict with keys: symbol, exchange,
    quote_type, currency, name. Returns None if no suitable match found.
    """
    sess = session or _get_session()
    url = "https://query1.finance.yahoo.com/v1/finance/search"
    params = {"q": isin, "quotesCount": 8, "newsCount": 0}

    try:
        resp = sess.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return None
        data: dict[str, Any] = resp.json()
    except Exception:
        return None

    quotes = data.get("quotes") or []
    if not quotes:
        return None

    def _rank(q: dict[str, Any]) -> tuple[int, int]:
        exch = q.get("exchange", "")
        qtype = q.get("quoteType", "")
        exch_rank = (
            _PREFERRED_EXCHANGES.index(exch)
            if exch in _PREFERRED_EXCHANGES
            else len(_PREFERRED_EXCHANGES)
        )
        type_rank = (
            _VALID_QUOTE_TYPES.index(qtype)
            if qtype in _VALID_QUOTE_TYPES
            else len(_VALID_QUOTE_TYPES)
        )
        return (type_rank, exch_rank)

    candidates = [q for q in quotes if q.get("symbol") and q.get("quoteType")]
    if not candidates:
        return None

    best = min(candidates, key=_rank)
    return {
        "symbol": best.get("symbol", ""),
        "exchange": best.get("exchange", ""),
        "quote_type": best.get("quoteType", ""),
        "currency": best.get("currency", "USD"),
        "name": best.get("shortname") or best.get("longname") or "",
    }


def resolve_yahoo_symbol(
    isin: str,
    *,
    override: Optional[str] = None,
    session: Optional[cffi_requests.Session] = None,
) -> Optional[str]:
    """Resolve an ISIN to a Yahoo Finance ticker symbol.

    Resolution order:
        1. Caller-provided override (e.g. from tax config `yfinance_ticker`)
        2. Curated known-good static map
        3. Yahoo Finance search API (live query)

    Returns None if no symbol could be resolved.
    """
    if override:
        return override
    known = get_known_symbol(isin)
    if known:
        return known
    found = search_yahoo_symbol(isin, session=session)
    return found["symbol"] if found else None
