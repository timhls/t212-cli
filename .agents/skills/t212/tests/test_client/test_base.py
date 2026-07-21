from datetime import datetime, timezone
import base64
import os
import time

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
        result = client.get_historical_dividends(limit=10, cursor="123", ticker="AAPL")
    assert result.items == []
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"limit": 10, "cursor": "123", "ticker": "AAPL"}


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
        result = client.get_historical_orders(limit=5, cursor="1", ticker="TSLA")
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
                    "instrument": {"ticker": "AAPL_US_EQ"},
                    "walletImpact": {
                        "currency": "USD",
                        "currentValue": 110.0,
                        "fxImpact": 0.0,
                        "totalCost": 100.0,
                        "unrealizedProfitLoss": 10.0,
                    },
                }
            ]
        ),
    ):
        result = client.get_positions(ticker="AAPL")
    assert len(result) == 1
    assert result[0].currentPrice == 110.0
    assert result[0].walletImpact is not None
    assert result[0].walletImpact.unrealizedProfitLoss == 10.0


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


# === Tests for client enhancements (Phase 2) ===


def test_validate_limit_clamps_above_50() -> None:
    from t212_cli.client.base import _validate_limit

    assert _validate_limit(100) == 50
    assert _validate_limit(51) == 50


def test_validate_limit_clamps_below_1() -> None:
    from t212_cli.client.base import _validate_limit

    assert _validate_limit(0) == 1
    assert _validate_limit(-5) == 1


def test_validate_limit_passes_valid_values() -> None:
    from t212_cli.client.base import _validate_limit

    assert _validate_limit(1) == 1
    assert _validate_limit(20) == 20
    assert _validate_limit(50) == 50


def test_cursor_unified_as_str(client: Trading212Client) -> None:
    """All three history methods accept cursor as Optional[str]."""
    import inspect

    for method_name in (
        "get_historical_dividends",
        "get_historical_orders",
        "get_historical_transactions",
    ):
        method = getattr(client, method_name)
        sig = inspect.signature(method)
        cursor_param = sig.parameters.get("cursor")
        assert cursor_param is not None, f"{method_name} missing cursor param"
        # Accept either typing.Optional[str] or "str | None"
        annotation_str = str(cursor_param.annotation)
        assert "str" in annotation_str, (
            f"{method_name}.cursor should accept str, got {annotation_str}"
        )


def test_cursor_from_next_page_path_extracts_cursor() -> None:
    from t212_cli.client.base import _cursor_from_next_page_path

    assert (
        _cursor_from_next_page_path(
            "/api/v0/equity/history/orders?limit=50&cursor=1760346100000"
        )
        == "1760346100000"
    )
    assert (
        _cursor_from_next_page_path(
            "/api/v0/equity/history/orders?limit=50&cursor=abc123"
        )
        == "abc123"
    )
    assert _cursor_from_next_page_path("/api/v0/equity/history/orders?limit=50") is None


def test_iter_all_orders_paginates_via_next_page_path(
    client: Trading212Client,
) -> None:
    """iter_all_orders follows nextPagePath until exhausted."""
    page1 = MagicMock()
    page1.items = [{"id": 1}, {"id": 2}]
    page1.nextPagePath = "/api/v0/equity/history/orders?limit=50&cursor=100"

    page2 = MagicMock()
    page2.items = [{"id": 3}]
    page2.nextPagePath = None

    with patch.object(
        client, "get_historical_orders", side_effect=[page1, page2]
    ) as mock_get:
        result = list(client.iter_all_orders())

    assert len(result) == 3
    assert mock_get.call_count == 2
    # Second call should pass the cursor extracted from nextPagePath
    second_call_kwargs = mock_get.call_args_list[1].kwargs
    assert second_call_kwargs.get("cursor") == "100"


def test_iter_all_orders_stops_when_next_page_null(
    client: Trading212Client,
) -> None:
    """iter_all_orders terminates when nextPagePath is None."""
    page1 = MagicMock()
    page1.items = [{"id": 1}]
    page1.nextPagePath = None

    with patch.object(client, "get_historical_orders", return_value=page1) as mock_get:
        result = list(client.iter_all_orders())

    assert len(result) == 1
    assert mock_get.call_count == 1


def test_iter_all_orders_stops_when_cursor_missing(
    client: Trading212Client,
) -> None:
    """iter_all_orders terminates gracefully if nextPagePath has no cursor param."""
    page1 = MagicMock()
    page1.items = [{"id": 1}]
    page1.nextPagePath = "/api/v0/equity/history/orders?limit=50"  # no cursor

    with patch.object(client, "get_historical_orders", return_value=page1) as mock_get:
        result = list(client.iter_all_orders())

    assert len(result) == 1
    assert mock_get.call_count == 1


def test_iter_all_dividends_paginates(client: Trading212Client) -> None:
    page1 = MagicMock()
    page1.items = [{"id": 1}]
    page1.nextPagePath = "/api/v0/equity/history/dividends?limit=50&cursor=xyz"

    page2 = MagicMock()
    page2.items = [{"id": 2}]
    page2.nextPagePath = None

    with patch.object(client, "get_historical_dividends", side_effect=[page1, page2]):
        result = list(client.iter_all_dividends())

    assert len(result) == 2


def test_iter_all_transactions_paginates(client: Trading212Client) -> None:
    page1 = MagicMock()
    page1.items = [{"id": 1}]
    page1.nextPagePath = None

    with patch.object(client, "get_historical_transactions", return_value=page1):
        result = list(client.iter_all_transactions())

    assert len(result) == 1


def test_wait_for_report_returns_when_finished(
    client: Trading212Client,
) -> None:
    """wait_for_report polls until status is Finished."""
    finished_report = MagicMock()
    finished_report.reportId = 42
    finished_report.status = MagicMock()
    finished_report.status.value = "Finished"
    finished_report.downloadLink = "https://example.com/report.csv"

    with patch.object(client, "get_historical_exports", return_value=[finished_report]):
        result = client.wait_for_report(42, timeout=10, poll_interval=0.01)

    assert result is finished_report


def test_wait_for_report_raises_on_failed_status(
    client: Trading212Client,
) -> None:
    """wait_for_report raises RuntimeError on Failed/Canceled status."""
    failed_report = MagicMock()
    failed_report.reportId = 42
    failed_report.status = MagicMock()
    failed_report.status.value = "Failed"

    with patch.object(client, "get_historical_exports", return_value=[failed_report]):
        with pytest.raises(RuntimeError, match="Failed"):
            client.wait_for_report(42, timeout=10, poll_interval=0.01)


def test_wait_for_report_raises_on_canceled_status(
    client: Trading212Client,
) -> None:
    canceled_report = MagicMock()
    canceled_report.reportId = 42
    canceled_report.status = MagicMock()
    canceled_report.status.value = "Canceled"

    with patch.object(client, "get_historical_exports", return_value=[canceled_report]):
        with pytest.raises(RuntimeError, match="Canceled"):
            client.wait_for_report(42, timeout=10, poll_interval=0.01)


def test_wait_for_report_raises_on_timeout(client: Trading212Client) -> None:
    """wait_for_report raises TimeoutError when no terminal state within timeout."""
    processing_report = MagicMock()
    processing_report.reportId = 42
    processing_report.status = MagicMock()
    processing_report.status.value = "Processing"

    with patch.object(
        client, "get_historical_exports", return_value=[processing_report]
    ):
        with pytest.raises(TimeoutError, match="not finished"):
            client.wait_for_report(42, timeout=0.05, poll_interval=0.02)


def test_wait_for_report_raises_when_report_id_missing(
    client: Trading212Client,
) -> None:
    """wait_for_report raises RuntimeError when reportId is not found in exports."""
    other_report = MagicMock()
    other_report.reportId = 99

    with patch.object(client, "get_historical_exports", return_value=[other_report]):
        with pytest.raises(RuntimeError, match="not found"):
            client.wait_for_report(42, timeout=10, poll_interval=0.01)


def test_get_historical_orders_applies_limit_validation(
    client: Trading212Client,
) -> None:
    """get_historical_orders clamps limit to 50 via _validate_limit."""
    with patch.object(
        client.client,
        "get",
        return_value=_mock_response({"items": [], "nextPagePath": None}),
    ) as mock_get:
        client.get_historical_orders(limit=1000)

    args, kwargs = mock_get.call_args
    params = kwargs.get("params") or {}
    assert params.get("limit") == 50


# === Rate-limit retry tests ===


def test_rate_limit_wait_seconds_prefers_reset_timestamp() -> None:
    """_rate_limit_wait_seconds computes wait from x-ratelimit-reset."""
    from t212_cli.client.base import _rate_limit_wait_seconds

    resp = MagicMock()
    resp.headers = {
        "x-ratelimit-reset": str(time.time() + 30),
        "Retry-After": "1",
    }
    wait = _rate_limit_wait_seconds(resp)
    assert 28 <= wait <= 32


def test_rate_limit_wait_seconds_falls_back_to_retry_after() -> None:
    """Falls back to Retry-After when x-ratelimit-reset is missing."""
    from t212_cli.client.base import _rate_limit_wait_seconds

    resp = MagicMock()
    resp.headers = {"Retry-After": "5"}
    assert _rate_limit_wait_seconds(resp) == 5.0


def test_rate_limit_wait_seconds_defaults_on_no_headers() -> None:
    """Uses exponential backoff default when neither header is present."""
    from t212_cli.client.base import (
        _rate_limit_wait_seconds,
        _RATE_LIMIT_INITIAL_BACKOFF,
    )

    resp = MagicMock()
    resp.headers = {}
    assert _rate_limit_wait_seconds(resp) == _RATE_LIMIT_INITIAL_BACKOFF


def test_get_retries_on_429_then_succeeds(client: Trading212Client) -> None:
    """_get retries on 429 and returns the successful response."""
    ok_response = _mock_response({"ok": True})
    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "0"}
    rate_limited.raise_for_status = MagicMock()

    with patch.object(client.client, "get", side_effect=[rate_limited, ok_response]):
        result = client.get_account_summary()

    assert result is not None


def test_get_raises_after_max_retries(client: Trading212Client) -> None:
    """_get raises after _RATE_LIMIT_MAX_RETRIES + 1 attempts."""

    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "0"}
    rate_limited.raise_for_status = MagicMock()

    with patch.object(client.client, "get", side_effect=[rate_limited]):
        with pytest.raises(Exception):
            client.get_account_summary()
