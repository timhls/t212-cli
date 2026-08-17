import csv
import datetime
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from t212_cli.tax.csv_report import (
    build_events,
    generate_csv_tax_report,
    parse_float,
)
from t212_cli.tax.models import AssetClass, TaxInstrument

COLUMNS = (
    "Action,Time (UTC),ISIN,Ticker,Name,Notes,ID,No. of shares,"
    "Price / share,Currency (Price / share),Exchange rate,Result,"
    "Currency (Result),Total,Currency (Total),Charge amount,"
    "Currency (Charge amount),Deposit fee,Currency (Deposit fee),"
    "Currency conversion fee,Currency (Currency conversion fee),"
    "Merchant name,Merchant category,ATM Withdrawal Fee"
).split(",")


def make_row(
    action: str,
    time: str = "2025-10-06 09:00:00+00:00",
    isin: str = "",
    ticker: str = "",
    name: str = "",
    notes: str = "",
    qty: str = "",
    price: str = "",
    cur: str = "",
    fx: str = "",
    result: str = "",
    result_cur: str = "",
    total: str = "",
    total_cur: str = "",
    fxfee: str = "",
    fxfee_cur: str = "",
) -> str:
    fields = {c: "" for c in COLUMNS}
    fields.update(
        {
            "Action": action,
            "Time (UTC)": time,
            "ISIN": isin,
            "Ticker": ticker,
            "Name": name,
            "Notes": notes,
            "ID": "ID1",
            "No. of shares": qty,
            "Price / share": price,
            "Currency (Price / share)": cur,
            "Exchange rate": fx,
            "Result": result,
            "Currency (Result)": result_cur,
            "Total": total,
            "Currency (Total)": total_cur,
            "Currency conversion fee": fxfee,
            "Currency (Currency conversion fee)": fxfee_cur,
        }
    )
    buf = io.StringIO()
    csv.writer(buf).writerow([fields[c] for c in COLUMNS])
    return buf.getvalue().rstrip("\r\n")


def parse_rows(lines: list[str]) -> list[dict[str, str]]:
    return list(csv.DictReader([",".join(COLUMNS), *lines]))


def write_csv(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "export.csv"
    path.write_text("\n".join([",".join(COLUMNS), *rows]) + "\n", encoding="utf-8")
    return path


def test_parse_float_handles_empty_and_quotes() -> None:
    assert parse_float(None) == 0.0
    assert parse_float("") == 0.0
    assert parse_float("  ") == 0.0
    assert parse_float('"12.50"') == 12.50
    assert parse_float("-3.14") == -3.14


@patch("t212_cli.tax.csv_report.get_instrument_config")
def test_build_events_basics(mock_get_config: MagicMock) -> None:
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.3
    )
    rows = [
        make_row(
            "Market buy",
            "2025-10-06 09:42:04+00:00",
            "IE00B4L5Y983",
            "EUNL",
            "World",
            qty="1.0",
            price="100.0",
            cur="EUR",
            fx="1.0",
            total="100.00",
            total_cur="EUR",
        ),
        make_row(
            "Transfer in",
            "2025-10-28 13:01:06+00:00",
            "LU0274211480",
            "XDAX",
            "DAX",
            qty="10.0",
            price="20.0",
            cur="EUR",
            fx="1.0",
            total="200.00",
            total_cur="EUR",
        ),
        make_row(
            "Market sell",
            "2025-12-30 08:04:00+00:00",
            "IE00B4L5Y983",
            "EUNL",
            "World",
            qty="1.0",
            price="110.0",
            cur="EUR",
            fx="1.0",
            result="10.00",
            result_cur="EUR",
            total="110.00",
            total_cur="EUR",
            fxfee="0.50",
            fxfee_cur="EUR",
        ),
        make_row(
            "Interest on cash",
            "2025-10-06 00:11:06+00:00",
            total="0.06",
            total_cur="EUR",
        ),
        make_row(
            "Lending interest",
            "2025-11-06 00:11:06+00:00",
            total="0.60",
            total_cur="EUR",
        ),
        make_row(
            "Spending cashback",
            "2025-11-07 00:11:06+00:00",
            total="1.00",
            total_cur="EUR",
        ),
        make_row(
            "Deposit", "2025-10-05 19:23:08+00:00", total="1000.00", total_cur="EUR"
        ),
    ]
    events, sells, transfers, cash_sums, warnings = build_events(parse_rows(rows))

    assert len(events) == 5  # 2 buys + 1 sell + 2 interest events
    assert len(sells) == 1
    assert sells[0].t212_result_eur == 10.00
    assert sells[0].net_proceeds_eur == pytest.approx(109.50)
    assert len(transfers) == 1
    assert transfers[0].value_eur == pytest.approx(200.0)
    assert cash_sums == {
        "Interest on cash": pytest.approx(0.06),
        "Lending interest": pytest.approx(0.60),
        "Spending cashback": pytest.approx(1.00),
    }
    assert warnings == []
    assert [e.type for e in events] == [
        "INTEREST",
        "BUY",
        "BUY",
        "INTEREST",
        "SELL",
    ]


@patch("t212_cli.tax.csv_report.get_instrument_config")
def test_broken_fx_buy_derived_from_result(mock_get_config: MagicMock) -> None:
    """Single-lot USD buy with Exchange rate 1.0 gets its EUR basis derived
    from the official T212 Result of the matching full sale."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIEN, tfs_quote=0.0
    )
    rows = [
        make_row(
            "Market buy",
            "2025-10-16 20:05:09+00:00",
            "US88160R1014",
            "TSLA",
            "Tesla",
            qty="0.5",
            price="429.75",
            cur="USD",
            fx="1.0",
            total="196.23",
            total_cur="USD",
        ),
        make_row(
            "Market sell",
            "2025-12-30 14:30:02+00:00",
            "US88160R1014",
            "TSLA",
            "Tesla",
            qty="0.5",
            price="460.90",
            cur="USD",
            fx="1.17604657",
            result="11.05",
            result_cur="EUR",
            total="178.68",
            total_cur="EUR",
            fxfee="0.27",
            fxfee_cur="EUR",
        ),
    ]
    events, _sells, _transfers, _cash, warnings = build_events(parse_rows(rows))

    buy = next(e for e in events if e.type == "BUY")
    sell = next(e for e in events if e.type == "SELL")
    expected_basis = (0.5 * (460.90 / 1.17604657) - 0.27 - 11.05) / 0.5
    assert buy.price_eur == pytest.approx(expected_basis, rel=1e-6)
    assert buy.fees_eur == 0.0
    assert sell.price_eur == pytest.approx(460.90 / 1.17604657)
    assert any("derived from T212 Result" in w for w in warnings)


@patch("t212_cli.tax.csv_report.get_instrument_config")
def test_broken_fx_buy_fx_fallback(mock_get_config: MagicMock) -> None:
    """Broken FX buy without a matching full sale falls back to a fetched
    historical FX rate."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIEN, tfs_quote=0.0
    )
    rows = [
        make_row(
            "Market buy",
            "2025-10-14 23:37:27+00:00",
            "US1725731079",
            "CRCL",
            "Circle",
            qty="2.0",
            price="135.44",
            cur="USD",
            fx="1.0",
            total="270.88",
            total_cur="USD",
        ),
        make_row(
            "Market buy",
            "2025-11-14 23:37:27+00:00",
            "US1725731079",
            "CRCL",
            "Circle",
            qty="1.0",
            price="140.00",
            cur="USD",
            fx="1.0",
            total="140.00",
            total_cur="USD",
        ),
    ]

    def fake_fx(currency: str, d: datetime.date) -> float | None:
        assert currency == "USD"
        return 1.1567

    events, _sells, _t, _c, warnings = build_events(
        parse_rows(rows), fx_fetcher=fake_fx
    )
    buys = [e for e in events if e.type == "BUY"]
    assert buys[0].price_eur == pytest.approx(135.44 / 1.1567)
    assert buys[1].price_eur == pytest.approx(140.00 / 1.1567)
    assert len([w for w in warnings if "approximated" in w]) == 2


@patch("t212_cli.tax.csv_report.get_instrument_config")
def test_dividend_row_built_net_with_warning(mock_get_config: MagicMock) -> None:
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.3
    )
    rows = [
        make_row(
            "Dividend",
            "2025-11-15 00:00:00+00:00",
            "US0378331005",
            "AAPL",
            "Apple",
            notes="Dividend from Apple Gross $0.25",
            total="0.19",
            total_cur="EUR",
        ),
    ]
    events, _sells, _t, _c, warnings = build_events(parse_rows(rows))
    div = next(e for e in events if e.type == "DIVIDEND")
    assert div.gross_amount_eur == pytest.approx(0.19)
    assert div.foreign_tax_eur == 0.0
    assert any("withholding" in w for w in warnings)


@patch("t212_cli.tax.calculator.get_instrument_config")
@patch("t212_cli.tax.csv_report.get_instrument_config")
def test_generate_csv_tax_report_end_to_end(
    mock_get_config: MagicMock,
    mock_calc_config: MagicMock,
    tmp_path: Path,
) -> None:
    """End-to-end: fund sale with TFS, ETC sale routed to §23, interest
    and cashback sums, no year-end holdings."""

    def config_by_isin(isin: str) -> TaxInstrument:
        if isin == "GB00ETC":
            return TaxInstrument(asset_class=AssetClass.SYNTHETIC_ETC, tfs_quote=0.0)
        return TaxInstrument(
            asset_class=AssetClass.AKTIENFONDS,
            tfs_quote=0.3,
            yfinance_ticker="FUND.DE",
        )

    mock_get_config.side_effect = config_by_isin
    mock_calc_config.side_effect = config_by_isin

    rows = [
        make_row(
            "Market buy",
            "2025-10-01 08:00:00+00:00",
            "IE00FUND",
            "FUND",
            "Fund",
            qty="10.0",
            price="100.0",
            cur="EUR",
            fx="1.0",
            total="1000.00",
            total_cur="EUR",
        ),
        make_row(
            "Market sell",
            "2025-12-30 08:04:00+00:00",
            "IE00FUND",
            "FUND",
            "Fund",
            qty="10.0",
            price="106.0",
            cur="EUR",
            fx="1.0",
            result="60.00",
            result_cur="EUR",
            total="1060.00",
            total_cur="EUR",
        ),
        make_row(
            "Market buy",
            "2025-10-15 07:00:01+00:00",
            "GB00ETC",
            "ETC",
            "Metals",
            qty="3.0",
            price="16.31",
            cur="USD",
            fx="1.16333808",
            total="42.12",
            total_cur="EUR",
            fxfee="0.06",
            fxfee_cur="EUR",
        ),
        make_row(
            "Market sell",
            "2025-12-30 08:00:01+00:00",
            "GB00ETC",
            "ETC",
            "Metals",
            qty="3.0",
            price="17.62",
            cur="USD",
            fx="1.17702",
            result="2.85",
            result_cur="EUR",
            total="44.84",
            total_cur="EUR",
            fxfee="0.07",
            fxfee_cur="EUR",
        ),
        make_row(
            "Interest on cash",
            "2025-12-06 00:11:06+00:00",
            total="3.61",
            total_cur="EUR",
        ),
        make_row(
            "Spending cashback",
            "2025-12-07 00:11:06+00:00",
            total="22.67",
            total_cur="EUR",
        ),
    ]
    csv_path = write_csv(tmp_path, rows)

    def fake_fx(currency: str, d: datetime.date) -> float | None:
        return 1.17

    with patch("t212_cli.tax.calculator.get_historical_price_eur") as mock_price:
        mock_price.return_value = 104.0
        report = generate_csv_tax_report(
            csv_path,
            2025,
            fx_fetcher=fake_fx,
            symbol_resolver=lambda isin: "FUND.DE",
        )

    # Fund: gain 60 brutto -> 42.00 after 30% TFS (+ interest 3.61)
    assert report.fifo_taxable_gains == pytest.approx(42.00 + 3.61)
    # ETC: FIFO via CSV FX rates differs slightly from T212's Result (2.85)
    assert report.sec23_gains == pytest.approx(2.71, abs=0.02)
    assert report.cash_sums["Interest on cash"] == pytest.approx(3.61)
    assert report.cash_sums["Spending cashback"] == pytest.approx(22.67)
    assert report.uncovered_sells == {}
    assert report.vorab_rows == []  # everything sold -> no year-end holdings
    assert len(report.inventory) == 0
    assert report.basiszins == 0.0253


@patch("t212_cli.tax.calculator.get_instrument_config")
@patch("t212_cli.tax.csv_report.get_instrument_config")
def test_generate_csv_tax_report_vorabpauschale(
    mock_get_config: MagicMock,
    mock_calc_config: MagicMock,
    tmp_path: Path,
) -> None:
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS,
        tfs_quote=0.3,
        yfinance_ticker="FUND.DE",
    )
    mock_calc_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS,
        tfs_quote=0.3,
        yfinance_ticker="FUND.DE",
    )
    rows = [
        make_row(
            "Market buy",
            "2025-10-01 08:00:00+00:00",
            "IE00FUND",
            "FUND",
            "Fund",
            qty="10.0",
            price="100.0",
            cur="EUR",
            fx="1.0",
            total="1000.00",
            total_cur="EUR",
        ),
        make_row(
            "Interest on cash",
            "2025-12-06 00:11:06+00:00",
            total="1.00",
            total_cur="EUR",
        ),
    ]
    csv_path = write_csv(tmp_path, rows)

    with patch("t212_cli.tax.calculator.get_historical_price_eur") as mock_price:
        mock_price.return_value = 104.0
        report = generate_csv_tax_report(
            csv_path, 2025, symbol_resolver=lambda isin: "FUND.DE"
        )

    # in-year buy (Oct): basisertrag = 100 * 0.0253 * 0.7 * 3/12
    # wertsteigerung since acquisition = 104 - 100 = 4 -> min = basisertrag
    expected = 10 * 100 * 0.0253 * 0.7 * 3 / 12
    assert len(report.vorab_rows) == 1
    assert report.vorab_rows[0].gross == pytest.approx(expected, rel=1e-4)
    assert report.vorab_rows[0].taxable == pytest.approx(expected * 0.7, rel=1e-4)
    assert report.vorab_taxable_total == pytest.approx(expected * 0.7, abs=0.01)
    assert report.inventory[0].quantity == pytest.approx(10.0)


def test_generate_csv_tax_report_unknown_basiszins(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        [
            make_row(
                "Deposit",
                "2030-01-01 00:00:00+00:00",
                total="1.00",
                total_cur="EUR",
            )
        ],
    )
    with pytest.raises(ValueError, match="Basiszins"):
        generate_csv_tax_report(csv_path, 2030)


@patch("t212_cli.tax.calculator.get_instrument_config")
@patch("t212_cli.tax.csv_report.get_instrument_config")
def test_uncovered_sell_produces_warning(
    mock_get_config: MagicMock,
    mock_calc_config: MagicMock,
    tmp_path: Path,
) -> None:
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.3
    )
    mock_calc_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.3
    )
    rows = [
        make_row(
            "Market sell",
            "2025-12-30 08:04:00+00:00",
            "IE00XFER",
            "XFER",
            "Transfer",
            qty="5.0",
            price="110.0",
            cur="EUR",
            fx="1.0",
            result="50.00",
            result_cur="EUR",
            total="550.00",
            total_cur="EUR",
        ),
    ]
    csv_path = write_csv(tmp_path, rows)
    report = generate_csv_tax_report(csv_path, 2025, symbol_resolver=lambda isin: None)
    assert report.uncovered_sells == {"IE00XFER": pytest.approx(5.0)}
    assert any("not covered" in w for w in report.warnings)
