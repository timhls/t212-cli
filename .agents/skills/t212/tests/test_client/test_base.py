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


def _mock_response(json_data: object) -> MagicMock:
    """Create a mock response with successful status."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.is_success = True
    resp.raise_for_status.return_value = None
    return resp


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


def test_get_request_uses_correct_url(client: Trading212Client) -> None:
    """Validate the full URL is constructed correctly from the base URL and endpoint."""
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response({"id": 1, "currencyCode": "EUR"}),
    ) as mock_get:
        client.get_account_summary()

    args, kwargs = mock_get.call_args
    called_url = args[0]
    assert called_url == "https://demo.trading212.com/api/v0/equity/account/summary"


def test_get_request_sends_authorization_header(client: Trading212Client) -> None:
    """Validate that GET requests include the Authorization header."""
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response({"id": 1, "currencyCode": "EUR"}),
    ):
        client.get_account_summary()

    assert "Authorization" in client.client.headers
    assert client.client.headers["Authorization"].startswith("Basic ")


def test_post_request_sends_authorization_header(client: Trading212Client) -> None:
    """Validate that POST requests include the Authorization header."""
    with patch.object(
        client.client, "post", return_value=_mock_response({"reportId": 1})
    ):
        req = PublicReportRequest(
            dataIncluded=ReportDataIncluded(includeDividends=True),
            timeFrom=datetime(2020, 1, 1, tzinfo=timezone.utc),
            timeTo=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )
        client.request_historical_export(req)

    assert "Authorization" in client.client.headers
    assert client.client.headers["Authorization"].startswith("Basic ")


def test_delete_request_sends_authorization_header(client: Trading212Client) -> None:
    """Validate that DELETE requests include the Authorization header."""
    with patch.object(client.client, "delete", return_value=_mock_response(None)):
        client.cancel_order(42)

    assert "Authorization" in client.client.headers
    assert client.client.headers["Authorization"].startswith("Basic ")


def test_get_account_summary(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response({"id": 123, "currencyCode": "EUR"}),
    ) as mock_get:
        result = client.get_account_summary()
    assert result.id == 123
    mock_get.assert_called_once()


def test_get_historical_dividends(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response({"items": [], "nextPagePath": None}),
    ) as mock_get:
        result = client.get_historical_dividends(limit=10, cursor=123, ticker="AAPL")
    assert result.items == []
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"limit": 10, "cursor": 123, "ticker": "AAPL"}


def test_get_historical_exports(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response([{"reportId": 1, "status": "Finished"}]),
    ):
        result = client.get_historical_exports()
    assert len(result) == 1
    assert result[0].reportId == 1


def test_request_historical_export(client: Trading212Client) -> None:
    with patch.object(
        client.client, "post", return_value=_mock_response({"reportId": 1})
    ):
        req = PublicReportRequest(
            dataIncluded=ReportDataIncluded(includeDividends=True),
            timeFrom=datetime(2020, 1, 1, tzinfo=timezone.utc),
            timeTo=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )
        result = client.request_historical_export(req)
    assert result.reportId == 1


def test_get_historical_orders(client: Trading212Client) -> None:
    with patch.object(client.client, "get", return_value=_mock_response({"items": []})):
        result = client.get_historical_orders(limit=5, cursor=1, ticker="TSLA")
    assert result.items == []


def test_get_historical_transactions(client: Trading212Client) -> None:
    with patch.object(client.client, "get", return_value=_mock_response({"items": []})):
        result = client.get_historical_transactions(limit=5, cursor="cur", time="2021")
    assert result.items == []


def test_get_exchanges(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            [{"id": 1, "name": "NASDAQ", "workingSchedules": []}]
        ),
    ):
        result = client.get_exchanges()
    assert len(result) == 1
    assert result[0].name == "NASDAQ"


def test_get_instruments(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            [
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
        ),
    ):
        result = client.get_instruments()
    assert len(result) == 1
    assert result[0].ticker == "AAPL"


def test_get_orders(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            [
                {
                    "id": 1,
                    "creationTime": "2021",
                    "quantity": 1,
                    "status": "NEW",
                    "ticker": "AAPL",
                    "type": "MARKET",
                }
            ]
        ),
    ):
        result = client.get_orders()
    assert len(result) == 1


def test_place_limit_order(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "post",
        return_value=_mock_response(
            {
                "id": 1,
                "creationTime": "2021",
                "quantity": 1,
                "status": "NEW",
                "ticker": "AAPL",
                "type": "LIMIT",
                "limitPrice": 100,
            }
        ),
    ):
        req = LimitRequest(
            ticker="AAPL", quantity=1, limitPrice=100, timeValidity=TimeValidity.DAY
        )
        result = client.place_limit_order(req)
    assert result.id == 1


def test_place_market_order(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "post",
        return_value=_mock_response(
            {
                "id": 1,
                "creationTime": "2021",
                "quantity": 1,
                "status": "NEW",
                "ticker": "AAPL",
                "type": "MARKET",
            }
        ),
    ):
        req = MarketRequest(ticker="AAPL", quantity=1, extendedHours=False)
        result = client.place_market_order(req)
    assert result.id == 1


def test_place_stop_order(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "post",
        return_value=_mock_response(
            {
                "id": 1,
                "creationTime": "2021",
                "quantity": 1,
                "status": "NEW",
                "ticker": "AAPL",
                "type": "STOP",
                "stopPrice": 100,
            }
        ),
    ):
        req = StopRequest(
            ticker="AAPL", quantity=1, stopPrice=100, timeValidity=TimeValidity.DAY
        )
        result = client.place_stop_order(req)
    assert result.id == 1


def test_place_stop_limit_order(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "post",
        return_value=_mock_response(
            {
                "id": 1,
                "creationTime": "2021",
                "quantity": 1,
                "status": "NEW",
                "ticker": "AAPL",
                "type": "STOP_LIMIT",
                "stopPrice": 100,
                "limitPrice": 100,
            }
        ),
    ):
        req = StopLimitRequest(
            ticker="AAPL",
            quantity=1,
            stopPrice=100,
            limitPrice=100,
            timeValidity=TimeValidity.DAY,
        )
        result = client.place_stop_limit_order(req)
    assert result.id == 1


def test_cancel_order(client: Trading212Client) -> None:
    with patch.object(
        client.client, "delete", return_value=_mock_response(None)
    ) as mock_delete:
        client.cancel_order(1)
    mock_delete.assert_called_once()


def test_get_order_by_id(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            {
                "id": 1,
                "creationTime": "2021",
                "quantity": 1,
                "status": "NEW",
                "ticker": "AAPL",
                "type": "MARKET",
            }
        ),
    ):
        result = client.get_order_by_id(1)
    assert result.id == 1


def test_get_pies(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response([{"id": 1, "progress": 0.5, "status": "AHEAD"}]),
    ):
        result = client.get_pies()
    assert len(result) == 1


def test_create_pie(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "post",
        return_value=_mock_response(
            {
                "settings": {
                    "dividendCashAction": "REINVEST",
                    "icon": "Default",
                    "name": "P1",
                },
                "instruments": [],
            }
        ),
    ):
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


def test_delete_pie(client: Trading212Client) -> None:
    with patch.object(
        client.client, "delete", return_value=_mock_response(None)
    ) as mock_delete:
        client.delete_pie(1)
    mock_delete.assert_called_once()


def test_get_pie_by_id(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            {
                "settings": {
                    "dividendCashAction": "REINVEST",
                    "icon": "Default",
                    "name": "P1",
                },
                "instruments": [],
            }
        ),
    ):
        result = client.get_pie_by_id(1)
    assert result is not None
    assert result.settings is not None
    assert result.settings.name == "P1"


def test_update_pie(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "post",
        return_value=_mock_response(
            {
                "settings": {
                    "dividendCashAction": "REINVEST",
                    "icon": "Default",
                    "name": "P1",
                },
                "instruments": [],
            }
        ),
    ):
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


def test_duplicate_pie(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "post",
        return_value=_mock_response(
            {
                "settings": {
                    "dividendCashAction": "REINVEST",
                    "icon": "Default",
                    "name": "P1",
                },
                "instruments": [],
            }
        ),
    ):
        req = DuplicateBucketRequest(icon="Default", name="P1")
        result = client.duplicate_pie(1, req)
    assert result is not None
    assert result.settings is not None
    assert result.settings.name == "P1"


def test_get_positions(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            [
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
        ),
    ):
        result = client.get_positions(ticker="AAPL")
    assert len(result) == 1
    assert result[0].currentPrice == 110.0


def test_resolve_ticker_from_isin(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            [
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
        ),
    ):
        result = client.resolve_ticker_from_isin("US0378331005")
    assert result == "AAPL"


def test_resolve_ticker_from_isin_not_found(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            [
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
        ),
    ):
        result = client.resolve_ticker_from_isin("UNKNOWN")
    assert result is None


def test_resolve_isin_from_ticker(client: Trading212Client) -> None:
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            [
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
        ),
    ):
        result = client.resolve_isin_from_ticker("AAPL")
    assert result == "US0378331005"


def test_resolve_uses_cache(client: Trading212Client) -> None:
    """Verify that resolution methods cache instruments (single API call)."""
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response(
            [
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
        ),
    ) as mock_get:
        client.resolve_ticker_from_isin("US0378331005")
        client.resolve_isin_from_ticker("AAPL")
        client.resolve_isins_from_tickers()
    mock_get.assert_called_once()
