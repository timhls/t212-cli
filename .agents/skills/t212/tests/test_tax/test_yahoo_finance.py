from datetime import date
from t212_cli.tax.yahoo_finance import get_historical_price, get_etf_funds_data
from unittest.mock import patch, MagicMock
import pandas as pd


@patch("t212_cli.tax.yahoo_finance.get_ticker")
def test_get_historical_price(mock_get_ticker: MagicMock) -> None:
    mock_ticker = MagicMock()
    mock_hist = MagicMock()
    mock_hist.empty = False

    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]).tz_localize("UTC")
    mock_hist.index = idx
    mock_hist.__getitem__.return_value = pd.Series([100.0, 105.0, 110.0], index=idx)

    mock_ticker.history.return_value = mock_hist
    mock_get_ticker.return_value = mock_ticker

    price = get_historical_price("TEST", date(2024, 1, 3))
    assert price == 105.0


@patch("t212_cli.tax.yahoo_finance.get_ticker")
def test_get_historical_price_empty(mock_get_ticker: MagicMock) -> None:
    mock_ticker = MagicMock()
    mock_hist = MagicMock()
    mock_hist.empty = True
    mock_ticker.history.return_value = mock_hist
    mock_get_ticker.return_value = mock_ticker

    price = get_historical_price("TEST", date(2024, 1, 3))
    assert price is None


@patch("t212_cli.tax.yahoo_finance.get_ticker")
def test_get_etf_funds_data(mock_get_ticker: MagicMock) -> None:
    mock_ticker = MagicMock()
    mock_fd = MagicMock()

    mock_th = pd.DataFrame(
        {"Name": ["NVIDIA Corp", "Apple Inc"], "Holding Percent": [0.0562, 0.0502]},
        index=["NVDA", "AAPL"],
    )
    mock_fd.top_holdings = mock_th

    mock_fd.sector_weightings = {
        "technology": 0.3124,
        "financial_services": 0.1511,
    }

    mock_fd.asset_classes = {
        "cashPosition": 0.0032,
        "stockPosition": 0.9964,
        "bondPosition": 0.0,
    }

    mock_fops = pd.DataFrame(
        {
            "XDWD.DE": [0.0012, 0.28, 292411.47],
            "Category Average": ["<NA>", "<NA>", "<NA>"],
        },
        index=[
            "Annual Report Expense Ratio",
            "Annual Holdings Turnover",
            "Total Net Assets",
        ],
    )
    mock_fd.fund_operations = mock_fops

    mock_ticker.funds_data = mock_fd
    mock_get_ticker.return_value = mock_ticker

    result = get_etf_funds_data("XDWD.DE")
    assert result is not None
    assert len(result["holdings"]) == 2
    assert result["holdings"][0]["symbol"] == "NVDA"
    assert result["holdings"][0]["name"] == "NVIDIA Corp"
    assert result["holdings"][0]["weight"] == 0.0562

    assert "Technology" in result["sector_weightings"]
    assert result["sector_weightings"]["Technology"] == 0.3124

    assert "cash" in result["asset_classes"]
    assert result["asset_classes"]["cash"] == 0.0032

    assert result["annual_report_expense_ratio"] == 0.0012


@patch("t212_cli.tax.yahoo_finance.get_ticker")
def test_get_etf_funds_data_no_data(mock_get_ticker: MagicMock) -> None:
    mock_ticker = MagicMock()
    from yfinance.exceptions import YFDataException

    type(mock_ticker).funds_data = property(
        lambda self: (_ for _ in ()).throw(YFDataException("No data"))
    )
    mock_get_ticker.return_value = mock_ticker

    result = get_etf_funds_data("UNKNOWN")
    assert result is None
