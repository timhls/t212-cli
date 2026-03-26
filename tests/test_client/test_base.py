from datetime import datetime, timezone
import base64
import os

import pytest
from unittest.mock import patch, MagicMock
from t212_cli.client.base import Trading212Client

from t212_cli.models import ReportDataIncluded, TimeValidity, DividendCashAction
from t212_cli.models import (
    LimitRequest,
    MarketRequest,
    StopRequest,
    StopLimitRequest,
    PublicReportRequest,
    PieRequest,
    DuplicateBucketRequest,
)


@pytest.fixture
def client() -> Trading212Client:
    """Create a client with demo URL (default when env var not set)."""
    with patch.dict(os.environ, {}, clear=True):
        return Trading212Client(api_key_id="test_key", secret_key="test_secret")


def test_client_authorization_header() -> None:
    """Validate that the Authorization header uses correct Basic auth (base64-encoded key:secret)."""
    api_key = "my_api_key"
    secret = "my_secret"
    client = Trading212Client(api_key_id=api_key, secret_key=secret)

    expected_credentials = base64.b64encode(f"{api_key}:{secret}".encode()).decode()
    expected_header = f"Basic {expected_credentials}"

    assert client.headers["Authorization"] == expected_header


def test_client_accept_header() -> None:
    """Validate that the Accept header is set to application/json."""
    client = Trading212Client(api_key_id="k", secret_key="s")
    assert client.headers["Accept"] == "application/json"


@patch("t212_cli.client.base.httpx.get")
def test_get_request_uses_correct_url(
    mock_get: MagicMock, client: Trading212Client
) -> None:
    """Validate the full URL is constructed correctly from the base URL and endpoint."""
    mock_get.return_value = MagicMock()
    mock_get.return_value.json.return_value = {"id": 1, "currencyCode": "EUR"}

    client.get_account_summary()

    args, kwargs = mock_get.call_args
    called_url = args[0]
    assert called_url == "https://demo.trading212.com/api/v0/equity/account/summary"


@patch("t212_cli.client.base.httpx.get")
def test_get_request_sends_authorization_header(
    mock_get: MagicMock, client: Trading212Client
) -> None:
    """Validate that GET requests include the Authorization header."""
    mock_get.return_value = MagicMock()
    mock_get.return_value.json.return_value = {"id": 1, "currencyCode": "EUR"}

    client.get_account_summary()

    _, kwargs = mock_get.call_args
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"].startswith("Basic ")


@patch("t212_cli.client.base.httpx.post")
def test_post_request_sends_authorization_header(
    mock_post: MagicMock, client: Trading212Client
) -> None:
    """Validate that POST requests include the Authorization header."""
    mock_post.return_value = MagicMock()
    mock_post.return_value.json.return_value = {"reportId": 1}

    req = PublicReportRequest(
        dataIncluded=ReportDataIncluded(includeDividends=True),
        timeFrom=datetime(2020, 1, 1, tzinfo=timezone.utc),
        timeTo=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )
    client.request_historical_export(req)

    _, kwargs = mock_post.call_args
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"].startswith("Basic ")


@patch("t212_cli.client.base.httpx.delete")
def test_delete_request_sends_authorization_header(
    mock_delete: MagicMock, client: Trading212Client
) -> None:
    """Validate that DELETE requests include the Authorization header."""
    mock_delete.return_value = MagicMock()

    client.cancel_order(42)

    _, kwargs = mock_delete.call_args
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"].startswith("Basic ")


@patch("t212_cli.client.base.httpx.get")
def test_get_account_summary(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 123, "currencyCode": "EUR"}
    mock_get.return_value = mock_response

    result = client.get_account_summary()
    assert result.id == 123
    mock_get.assert_called_once()


@patch("t212_cli.client.base.httpx.get")
def test_get_historical_dividends(
    mock_get: MagicMock, client: Trading212Client
) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"items": [], "nextPagePath": None}
    mock_get.return_value = mock_response

    result = client.get_historical_dividends(limit=10, cursor=123, ticker="AAPL")
    assert result.items == []
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert kwargs["params"] == {"limit": 10, "cursor": 123, "ticker": "AAPL"}


@patch("t212_cli.client.base.httpx.get")
def test_get_historical_exports(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = [{"reportId": 1, "status": "Finished"}]
    mock_get.return_value = mock_response

    result = client.get_historical_exports()
    assert len(result) == 1
    assert result[0].reportId == 1


@patch("t212_cli.client.base.httpx.post")
def test_request_historical_export(
    mock_post: MagicMock, client: Trading212Client
) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"reportId": 1}
    mock_post.return_value = mock_response

    req = PublicReportRequest(
        dataIncluded=ReportDataIncluded(includeDividends=True),
        timeFrom=datetime(2020, 1, 1, tzinfo=timezone.utc),
        timeTo=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )
    result = client.request_historical_export(req)
    assert result.reportId == 1


@patch("t212_cli.client.base.httpx.get")
def test_get_historical_orders(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"items": []}
    mock_get.return_value = mock_response

    result = client.get_historical_orders(limit=5, cursor=1, ticker="TSLA")
    assert result.items == []


@patch("t212_cli.client.base.httpx.get")
def test_get_historical_transactions(
    mock_get: MagicMock, client: Trading212Client
) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"items": []}
    mock_get.return_value = mock_response

    result = client.get_historical_transactions(limit=5, cursor="cur", time="2021")
    assert result.items == []


@patch("t212_cli.client.base.httpx.get")
def test_get_exchanges(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"id": 1, "name": "NASDAQ", "workingSchedules": []}
    ]
    mock_get.return_value = mock_response

    result = client.get_exchanges()
    assert len(result) == 1
    assert result[0].name == "NASDAQ"


@patch("t212_cli.client.base.httpx.get")
def test_get_instruments(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "ticker": "AAPL",
            "currencyCode": "USD",
            "name": "Apple",
            "shortName": "AAPL",
            "type": "STOCK",
            "workingScheduleId": 1,
            "isin": "US0378331005",
        }
    ]
    mock_get.return_value = mock_response

    result = client.get_instruments()
    assert len(result) == 1
    assert result[0].ticker == "AAPL"


@patch("t212_cli.client.base.httpx.get")
def test_get_orders(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "id": 1,
            "creationTime": "2021",
            "quantity": 1,
            "status": "NEW",
            "ticker": "AAPL",
            "type": "MARKET",
        }
    ]
    mock_get.return_value = mock_response

    result = client.get_orders()
    assert len(result) == 1


@patch("t212_cli.client.base.httpx.post")
def test_place_limit_order(mock_post: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": 1,
        "creationTime": "2021",
        "quantity": 1,
        "status": "NEW",
        "ticker": "AAPL",
        "type": "LIMIT",
        "limitPrice": 100,
    }
    mock_post.return_value = mock_response

    req = LimitRequest(
        ticker="AAPL", quantity=1, limitPrice=100, timeValidity=TimeValidity.DAY
    )
    result = client.place_limit_order(req)
    assert result.id == 1


@patch("t212_cli.client.base.httpx.post")
def test_place_market_order(mock_post: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": 1,
        "creationTime": "2021",
        "quantity": 1,
        "status": "NEW",
        "ticker": "AAPL",
        "type": "MARKET",
    }
    mock_post.return_value = mock_response

    req = MarketRequest(ticker="AAPL", quantity=1, extendedHours=False)
    result = client.place_market_order(req)
    assert result.id == 1


@patch("t212_cli.client.base.httpx.post")
def test_place_stop_order(mock_post: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": 1,
        "creationTime": "2021",
        "quantity": 1,
        "status": "NEW",
        "ticker": "AAPL",
        "type": "STOP",
        "stopPrice": 100,
    }
    mock_post.return_value = mock_response

    req = StopRequest(
        ticker="AAPL", quantity=1, stopPrice=100, timeValidity=TimeValidity.DAY
    )
    result = client.place_stop_order(req)
    assert result.id == 1


@patch("t212_cli.client.base.httpx.post")
def test_place_stop_limit_order(mock_post: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": 1,
        "creationTime": "2021",
        "quantity": 1,
        "status": "NEW",
        "ticker": "AAPL",
        "type": "STOP_LIMIT",
        "stopPrice": 100,
        "limitPrice": 100,
    }
    mock_post.return_value = mock_response

    req = StopLimitRequest(
        ticker="AAPL",
        quantity=1,
        stopPrice=100,
        limitPrice=100,
        timeValidity=TimeValidity.DAY,
    )
    result = client.place_stop_limit_order(req)
    assert result.id == 1


@patch("t212_cli.client.base.httpx.delete")
def test_cancel_order(mock_delete: MagicMock, client: Trading212Client) -> None:
    client.cancel_order(1)
    mock_delete.assert_called_once()


@patch("t212_cli.client.base.httpx.get")
def test_get_order_by_id(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": 1,
        "creationTime": "2021",
        "quantity": 1,
        "status": "NEW",
        "ticker": "AAPL",
        "type": "MARKET",
    }
    mock_get.return_value = mock_response

    result = client.get_order_by_id(1)
    assert result.id == 1


@patch("t212_cli.client.base.httpx.get")
def test_get_pies(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": 1, "progress": 0.5, "status": "AHEAD"}]
    mock_get.return_value = mock_response

    result = client.get_pies()
    assert len(result) == 1


@patch("t212_cli.client.base.httpx.post")
def test_create_pie(mock_post: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "settings": {"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"},
        "instruments": [],
    }
    mock_post.return_value = mock_response

    req = PieRequest(
        dividendCashAction=DividendCashAction.REINVEST,
        goal=0.0,
        icon="Default",
        name="P1",
        instrumentShares={},
    )
    result = client.create_pie(req)
    assert result is not None
    assert result.settings is not None
    assert result.settings.name == "P1"


@patch("t212_cli.client.base.httpx.delete")
def test_delete_pie(mock_delete: MagicMock, client: Trading212Client) -> None:
    client.delete_pie(1)
    mock_delete.assert_called_once()


@patch("t212_cli.client.base.httpx.get")
def test_get_pie_by_id(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "settings": {"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"},
        "instruments": [],
    }
    mock_get.return_value = mock_response

    result = client.get_pie_by_id(1)
    assert result is not None
    assert result.settings is not None
    assert result.settings.name == "P1"


@patch("t212_cli.client.base.httpx.post")
def test_update_pie(mock_post: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "settings": {"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"},
        "instruments": [],
    }
    mock_post.return_value = mock_response

    req = PieRequest(
        dividendCashAction=DividendCashAction.REINVEST,
        goal=0.0,
        icon="Default",
        name="P1",
        instrumentShares={},
    )
    result = client.update_pie(1, req)
    assert result is not None
    assert result.settings is not None
    assert result.settings.name == "P1"


@patch("t212_cli.client.base.httpx.post")
def test_duplicate_pie(mock_post: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "settings": {"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"},
        "instruments": [],
    }
    mock_post.return_value = mock_response

    req = DuplicateBucketRequest(icon="Default", name="P1")
    result = client.duplicate_pie(1, req)
    assert result is not None
    assert result.settings is not None
    assert result.settings.name == "P1"


@patch("t212_cli.client.base.httpx.get")
def test_get_positions(mock_get: MagicMock, client: Trading212Client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "ticker": "AAPL",
            "quantity": 1.0,
            "averagePrice": 100.0,
            "currentPrice": 110.0,
            "ppl": 10.0,
            "fxPpl": 0.0,
            "initialFillDate": "2021",
            "frontend": "W",
            "instrument": {"ticker": "AAPL_US_EQ"},
        }
    ]
    mock_get.return_value = mock_response

    result = client.get_positions(ticker="AAPL")
    assert len(result) == 1
    # Check currentPrice or another valid attribute since ticker might not be mapped directly
    assert result[0].currentPrice == 110.0
