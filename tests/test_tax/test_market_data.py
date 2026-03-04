from datetime import date
from t212_cli.tax.market_data import get_historical_price
from unittest.mock import patch, MagicMock
import pandas as pd


@patch("t212_cli.tax.market_data.yf.Ticker")
def test_get_historical_price(mock_ticker: MagicMock) -> None:
    mock_hist = MagicMock()
    # Mocking pandas dataframe
    mock_hist.empty = False

    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]).tz_localize("UTC")
    mock_hist.index = idx
    mock_hist.__getitem__.return_value = pd.Series([100.0, 105.0, 110.0], index=idx)

    mock_ticker.return_value.history.return_value = mock_hist

    # Target date is Jan 3
    price = get_historical_price("TEST", date(2024, 1, 3))
    assert price == 105.0


@patch("t212_cli.tax.market_data.yf.Ticker")
def test_get_historical_price_empty(mock_ticker: MagicMock) -> None:
    mock_hist = MagicMock()
    mock_hist.empty = True
    mock_ticker.return_value.history.return_value = mock_hist

    price = get_historical_price("TEST", date(2024, 1, 3))
    assert price is None
