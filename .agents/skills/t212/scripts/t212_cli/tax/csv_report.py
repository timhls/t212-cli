"""German tax report based on an official Trading 212 CSV export.

The CSV export is the authoritative data source for tax reporting because
the Public API does not return "Transfer in" (securities transfers from
other brokers) as rated fills, which silently breaks FIFO matching.

Known CSV quirks handled here:
- USD trades executed in extended hours can carry ``Exchange rate = 1.0``
  and no EUR conversion. For single-lot positions the EUR basis is derived
  from the official T212 "Result" column; otherwise a historical FX rate
  (e.g. EURUSD=X) is used as a fallback.
- "Transfer in" rows are treated as buys at the transfer valuation. If the
  original acquisition data from the outgoing broker is available, the FIFO
  basis should be corrected manually.
"""

import csv
import datetime
from collections.abc import Iterable
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel

from t212_cli.tax.calculator import FifoEngine, TaxEvent
from t212_cli.tax.config import get_instrument_config, update_instrument_config
from t212_cli.tax.models import AssetClass, TaxInstrument
from t212_cli.tax.yahoo_finance import get_fx_rate_to_eur
from t212_cli.tax.yahoo_symbols import resolve_yahoo_symbol

BASISZINS_BY_YEAR: dict[int, float] = {
    2023: 0.0255,
    2024: 0.0229,
    2025: 0.0253,
}

FUND_ASSET_CLASSES = (
    AssetClass.AKTIENFONDS,
    AssetClass.MISCHFONDS,
    AssetClass.IMMOBILIENFONDS,
    AssetClass.SONSTIGER_FONDS,
)

BUY_ACTIONS = {"Market buy", "Limit buy", "Transfer in"}
SELL_ACTIONS = {"Market sell", "Limit sell"}

FxRateFetcher = Callable[[str, datetime.date], Optional[float]]
SymbolResolver = Callable[[str], Optional[str]]


class SellDetail(BaseModel):
    date: datetime.datetime
    isin: str
    ticker: str
    quantity: float
    net_proceeds_eur: float
    t212_result_eur: float
    asset_class: str


class VorabRow(BaseModel):
    isin: str
    quantity: float
    gross: float
    tfs_quote: float
    taxable: float


class TransferIn(BaseModel):
    date: datetime.datetime
    isin: str
    ticker: str
    quantity: float
    value_eur: float


class InventoryRow(BaseModel):
    isin: str
    name: str
    quantity: float
    cost_eur: float


class CsvTaxReport(BaseModel):
    year: int
    basiszins: float
    cash_sums: dict[str, float]
    sells: list[SellDetail]
    transfers_in: list[TransferIn]
    fifo_taxable_gains: float
    aktien_verluste: float
    sonstige_verluste: float
    sec23_gains: float
    vorab_rows: list[VorabRow]
    vorab_taxable_total: float
    year_taxable_gains_with_vorab: float
    uncovered_sells: dict[str, float]
    inventory: list[InventoryRow]
    warnings: list[str]


def parse_float(value: Optional[str]) -> float:
    if value is None:
        return 0.0
    cleaned = value.strip().replace('"', "")
    if not cleaned:
        return 0.0
    return float(cleaned)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _row_datetime(row: dict[str, str]) -> datetime.datetime:
    return datetime.datetime.fromisoformat(row["Time (UTC)"])


def _price_eur(row: dict[str, str]) -> tuple[float, str, bool]:
    price = parse_float(row["Price / share"])
    currency = (row.get("Currency (Price / share)") or "").strip()
    fx = parse_float(row["Exchange rate"]) or 1.0
    broken = currency not in ("", "EUR") and abs(fx - 1.0) < 1e-9
    return (price / fx if currency != "EUR" else price), currency, broken


def _dividend_amounts(row: dict[str, str]) -> tuple[float, float]:
    """CSV dividend rows carry the PAID amount (net after withholding) in
    account currency in the Total column; Gross/Tax inside Notes are quoted
    in the trade currency and cannot be converted without FX. The event is
    therefore built net with a warning (conservative)."""
    return parse_float(row["Total"]), 0.0


def build_events(
    rows: Iterable[dict[str, str]],
    fx_fetcher: Optional[FxRateFetcher] = None,
) -> tuple[
    list[TaxEvent], list[SellDetail], list[TransferIn], dict[str, float], list[str]
]:
    """Build FIFO events from CSV rows.

    Returns (events, sell_details, transfers_in, cash_sums, warnings).
    """
    rows = list(rows)
    warnings: list[str] = []
    events: list[TaxEvent] = []
    sells: list[SellDetail] = []
    transfers: list[TransferIn] = []
    cash_sums: dict[str, float] = {}
    names: dict[str, str] = {}

    trade_rows = [
        r
        for r in rows
        if r["Action"] in BUY_ACTIONS | SELL_ACTIONS and (r.get("ISIN") or "").strip()
    ]

    for row in rows:
        action = row["Action"]
        isin = (row.get("ISIN") or "").strip()
        if isin and row.get("Name"):
            names.setdefault(isin, row["Name"])
        if action in ("Interest on cash", "Lending interest", "Spending cashback"):
            cash_sums[action] = cash_sums.get(action, 0.0) + parse_float(row["Total"])
            if action in ("Interest on cash", "Lending interest"):
                events.append(
                    TaxEvent(
                        date=_row_datetime(row),
                        type="INTEREST",
                        isin="",
                        gross_amount_eur=parse_float(row["Total"]),
                    )
                )
        elif action.startswith("Dividend") and isin:
            gross, foreign_tax = _dividend_amounts(row)
            if foreign_tax <= 0:
                warnings.append(
                    f"Dividend on {_row_datetime(row).date()} ({isin}): "
                    "no withholding tax parsed; treated as fully taxable"
                )
            events.append(
                TaxEvent(
                    date=_row_datetime(row),
                    type="DIVIDEND",
                    isin=isin,
                    gross_amount_eur=gross,
                    foreign_tax_eur=foreign_tax,
                )
            )

    broken_buys = [
        r for r in trade_rows if r["Action"] in BUY_ACTIONS and _price_eur(r)[2]
    ]
    for row in trade_rows:
        action = row["Action"]
        isin = row["ISIN"]
        quantity = parse_float(row["No. of shares"])
        price_eur, currency, broken = _price_eur(row)
        fees = parse_float(row["Currency conversion fee"])
        when = _row_datetime(row)
        if action in BUY_ACTIONS:
            if action == "Transfer in":
                transfers.append(
                    TransferIn(
                        date=when,
                        isin=isin,
                        ticker=row.get("Ticker") or "",
                        quantity=quantity,
                        value_eur=quantity * price_eur,
                    )
                )
            events.append(
                TaxEvent(
                    date=when,
                    type="BUY",
                    isin=isin,
                    quantity=quantity,
                    price_eur=price_eur,
                    fees_eur=fees,
                )
            )
        else:
            sells.append(
                SellDetail(
                    date=when,
                    isin=isin,
                    ticker=row.get("Ticker") or "",
                    quantity=quantity,
                    net_proceeds_eur=quantity * price_eur - fees,
                    t212_result_eur=parse_float(row["Result"]),
                    asset_class="",
                )
            )
            events.append(
                TaxEvent(
                    date=when,
                    type="SELL",
                    isin=isin,
                    quantity=quantity,
                    price_eur=price_eur,
                    fees_eur=fees,
                )
            )

    for buy in broken_buys:
        isin = buy["ISIN"]
        quantity = parse_float(buy["No. of shares"])
        when = _row_datetime(buy)
        derived = _derive_broken_fx_basis(
            isin=isin,
            quantity=quantity,
            when=when,
            trade_rows=trade_rows,
        )
        if derived is not None:
            for event in events:
                if (
                    event.isin == isin
                    and event.type == "BUY"
                    and abs(event.date - when) < datetime.timedelta(seconds=1)
                ):
                    event.price_eur = derived / quantity
                    event.fees_eur = 0.0
            warnings.append(
                f"Broken FX row ({buy.get('Ticker') or isin}, {when.date()}): "
                "EUR basis derived from T212 Result column"
            )
        elif fx_fetcher is not None:
            currency = (buy.get("Currency (Price / share)") or "").strip()
            rate = fx_fetcher(currency, when.date())
            if rate:
                for event in events:
                    if (
                        event.isin == isin
                        and event.type == "BUY"
                        and abs(event.date - when) < datetime.timedelta(seconds=1)
                    ):
                        event.price_eur = parse_float(buy["Price / share"]) / rate
                warnings.append(
                    f"Broken FX row ({buy.get('Ticker') or isin}, {when.date()}): "
                    f"EUR basis approximated via {currency}EUR=X"
                )
            else:
                warnings.append(
                    f"Broken FX row ({buy.get('Ticker') or isin}, {when.date()}): "
                    "no repair possible, kept raw price (unreliable!)"
                )

    events.sort(key=lambda e: e.date)
    for sell in sells:
        config = get_instrument_config(sell.isin)
        sell.asset_class = str(config.asset_class.value) if config else "Unknown"
    return events, sells, transfers, cash_sums, warnings


def _derive_broken_fx_basis(
    isin: str,
    quantity: float,
    when: datetime.datetime,
    trade_rows: list[dict[str, str]],
) -> Optional[float]:
    buys = [r for r in trade_rows if r["ISIN"] == isin and r["Action"] in BUY_ACTIONS]
    sells = [r for r in trade_rows if r["ISIN"] == isin and r["Action"] in SELL_ACTIONS]
    if len(buys) != 1 or len(sells) != 1:
        return None
    buy_qty = parse_float(buys[0]["No. of shares"])
    sell_qty = parse_float(sells[0]["No. of shares"])
    if abs(buy_qty - quantity) > 1e-9 or abs(sell_qty - buy_qty) > 1e-9:
        return None
    sell_row = sells[0]
    price_eur, _currency, _broken = _price_eur(sell_row)
    net_proceeds = sell_qty * price_eur - parse_float(
        sell_row["Currency conversion fee"]
    )
    return net_proceeds - parse_float(sell_row["Result"])


def resolve_inventory_symbols(
    engine: FifoEngine, symbol_resolver: Optional[SymbolResolver] = None
) -> list[str]:
    """Resolve and persist yfinance symbols for held funds lacking one."""
    warnings: list[str] = []
    if symbol_resolver is None:
        symbol_resolver = resolve_yahoo_symbol
    for isin, tranches in engine.inventory.items():
        if not tranches:
            continue
        config = get_instrument_config(isin)
        if not config or config.asset_class not in FUND_ASSET_CLASSES:
            continue
        if config.yfinance_ticker:
            continue
        try:
            symbol = symbol_resolver(isin)
        except Exception:  # nosec B110
            symbol = None
        if not symbol:
            warnings.append(
                f"Vorabpauschale skipped for {isin}: no Yahoo symbol resolvable"
            )
            continue
        update_instrument_config(
            isin,
            TaxInstrument(
                name=config.name,
                asset_class=config.asset_class,
                tfs_quote=config.tfs_quote,
                yfinance_ticker=symbol,
            ),
        )
    return warnings


def generate_csv_tax_report(
    path: Path,
    year: int,
    basiszins: Optional[float] = None,
    fx_fetcher: Optional[FxRateFetcher] = None,
    symbol_resolver: Optional[SymbolResolver] = None,
) -> CsvTaxReport:
    rows = load_rows(path)
    if fx_fetcher is None:
        fx_fetcher = get_fx_rate_to_eur
    if basiszins is None:
        basiszins = BASISZINS_BY_YEAR.get(year, 0.0)
        if basiszins == 0.0:
            raise ValueError(
                f"No Basiszins known for {year}; pass --basiszins explicitly"
            )

    events, sells, transfers, cash_sums, warnings = build_events(
        rows, fx_fetcher=fx_fetcher
    )

    engine = FifoEngine(target_year=year)
    for event in events:
        engine.process_event(event)

    for isin, qty in engine.uncovered_sells.items():
        warnings.append(
            f"Sell of {qty:.6f} shares ({isin}) not covered by buys/transfers "
            "in the CSV — FIFO result incomplete. Export the full account "
            "history or fix Transfer-in data."
        )

    warnings.extend(resolve_inventory_symbols(engine, symbol_resolver))

    vorab_before = {
        isin: [t.accumulated_vorabpauschale for t in tranches]
        for isin, tranches in engine.inventory.items()
    }
    try:
        engine.process_year_end(year, basiszins)
    except Exception as exc:  # nosec B110
        warnings.append(f"Vorabpauschale failed: {exc}")
    warnings.extend(
        f"Vorabpauschale skipped: {msg}" for msg in engine.price_fetch_failures
    )

    vorab_rows: list[VorabRow] = []
    for isin, tranches in sorted(engine.inventory.items()):
        if not tranches:
            continue
        config = get_instrument_config(isin)
        if not config or config.asset_class not in FUND_ASSET_CLASSES:
            continue
        before = vorab_before.get(isin, [])
        gross = sum(
            t.accumulated_vorabpauschale - b
            for t, b in zip(tranches, before, strict=False)
        )
        if gross <= 0:
            continue
        vorab_rows.append(
            VorabRow(
                isin=isin,
                quantity=sum(t.quantity for t in tranches),
                gross=round(gross, 4),
                tfs_quote=config.tfs_quote,
                taxable=round(gross * (1.0 - config.tfs_quote), 4),
            )
        )

    vorab_taxable_total = sum(r.taxable for r in vorab_rows)
    names = {
        r["ISIN"]: r["Name"]
        for r in rows
        if (r.get("ISIN") or "").strip() and r.get("Name")
    }
    inventory = [
        InventoryRow(
            isin=isin,
            name=names.get(isin, ""),
            quantity=round(sum(t.quantity for t in tranches), 6),
            cost_eur=round(sum(t.quantity * t.price_eur for t in tranches), 2),
        )
        for isin, tranches in sorted(engine.inventory.items())
        if tranches
    ]

    return CsvTaxReport(
        year=year,
        basiszins=basiszins,
        cash_sums=cash_sums,
        sells=sells,
        transfers_in=transfers,
        fifo_taxable_gains=round(engine.year_taxable_gains - vorab_taxable_total, 2),
        aktien_verluste=round(engine.year_aktien_verlust_generated, 2),
        sonstige_verluste=round(engine.year_sonstige_verlust_generated, 2),
        sec23_gains=round(engine.year_private_veraeusserungs_gewinne_generated, 2),
        vorab_rows=vorab_rows,
        vorab_taxable_total=round(vorab_taxable_total, 2),
        year_taxable_gains_with_vorab=round(engine.year_taxable_gains, 2),
        uncovered_sells=dict(engine.uncovered_sells),
        inventory=inventory,
        warnings=warnings,
    )
