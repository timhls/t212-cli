import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from t212_cli.client.cards import (
    CardsClient,
    CardSessionExpiredError,
    cookie_header_from_raw,
    cookie_header_from_state_file,
    resolve_cookie_header,
)

UTC = timezone.utc

SESSION_COOKIE = "TRADING212_SESSION_LIVE=abc123"
LOGIN_COOKIE = "LOGIN_TOKEN=xyz789"


def _storage_state(path: Path, include_session: bool = True) -> None:
    cookies = [
        {"name": "COOKIES_CONSENT", "value": "1", "domain": ".trading212.com"},
        {"name": "GEOLOCATION", "value": "DE", "domain": ".trading212.com"},
    ]
    if include_session:
        cookies.append(
            {
                "name": "TRADING212_SESSION_LIVE",
                "value": "abc123",
                "domain": ".trading212.com",
            }
        )
        cookies.append(
            {"name": "LOGIN_TOKEN", "value": "xyz789", "domain": ".trading212.com"}
        )
    path.write_text(json.dumps({"cookies": cookies, "origins": []}), encoding="utf-8")


class TestCookieLoading:
    def test_state_file_extract_session_and_login_token(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        _storage_state(state)
        header = cookie_header_from_state_file(state)
        assert "TRADING212_SESSION_LIVE=abc123" in header
        assert "LOGIN_TOKEN=xyz789" in header

    def test_state_file_without_session_cookie_raises(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        _storage_state(state, include_session=False)
        with pytest.raises(ValueError, match="TRADING212_SESSION_LIVE"):
            cookie_header_from_state_file(state)

    def test_state_file_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            cookie_header_from_state_file(tmp_path / "nope.json")

    def test_raw_header_strips_cookie_prefix(self) -> None:
        assert cookie_header_from_raw(f"Cookie: {SESSION_COOKIE}; {LOGIN_COOKIE}") == (
            f"{SESSION_COOKIE}; {LOGIN_COOKIE}"
        )

    def test_raw_header_without_primary_cookie_raises(self) -> None:
        with pytest.raises(ValueError, match="TRADING212_SESSION_LIVE"):
            cookie_header_from_raw("COOKIES_CONSENT=1")

    def test_resolve_explicit_file_wins(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        _storage_state(state)
        with patch.dict(
            "os.environ",
            {
                "T212_CARDS_COOKIE_FILE": "/nonexistent-from-env.json",
                "T212_CARDS_COOKIES": SESSION_COOKIE,
            },
        ):
            assert cookie_header_from_state_file(state) == resolve_cookie_header(
                cookie_file=str(state)
            )

    def test_resolve_env_file_used_when_no_args(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        _storage_state(state)
        with patch.dict("os.environ", {"T212_CARDS_COOKIE_FILE": str(state)}):
            assert resolve_cookie_header() == f"{SESSION_COOKIE}; {LOGIN_COOKIE}"

    def test_resolve_env_raw_used_last(self) -> None:
        with patch.dict("os.environ", {"T212_CARDS_COOKIES": SESSION_COOKIE}):
            assert resolve_cookie_header() == SESSION_COOKIE

    def test_resolve_nothing_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="session cookies"):
                resolve_cookie_header()


class TestCardsClient:
    def _client(self) -> CardsClient:
        return CardsClient(cookie_header=SESSION_COOKIE)

    def test_cookie_header_sent(self) -> None:
        client = self._client()
        assert client.client.headers["Cookie"] == SESSION_COOKIE

    def test_base_url_env_override(self) -> None:
        with patch.dict(
            "os.environ", {"T212_CARDS_BASE_URL": "http://localhost:1/v1/"}
        ):
            client = CardsClient(cookie_header=SESSION_COOKIE)
        assert client.base_url == "http://localhost:1/v1"

    def _response(self, json_data: object, status_code: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data
        resp.raise_for_status.return_value = None
        return resp

    def test_page_size_clamped_to_50(self) -> None:
        client = self._client()
        with patch.object(
            client.client, "get", return_value=self._response([])
        ) as mocked:
            client.get_transactions_page(page_size=500)
        mocked.assert_called_once()
        assert mocked.call_args.kwargs["params"] == {"pageSize": 50}

    def test_cursor_id_passed_through(self) -> None:
        client = self._client()
        with patch.object(
            client.client, "get", return_value=self._response([])
        ) as mocked:
            client.get_transactions_page(cursor_id=42)
        assert mocked.call_args.kwargs["params"] == {"pageSize": 50, "cursorId": 42}

    def test_unauthorized_raises_session_expired(self) -> None:
        client = self._client()
        with patch.object(
            client.client, "get", return_value=self._response({}, status_code=401)
        ):
            with pytest.raises(CardSessionExpiredError, match="session has expired"):
                client.get_transactions_page()

    def test_forbidden_raises_session_expired(self) -> None:
        client = self._client()
        with patch.object(
            client.client, "get", return_value=self._response({}, status_code=403)
        ):
            with pytest.raises(CardSessionExpiredError):
                client.get_transactions_page()


def _tx(
    tx_id: int, created: str, amount: float = 10.0, **overrides: object
) -> dict[str, object]:
    base = {
        "id": tx_id,
        "amount": amount,
        "billingAmount": amount,
        "currencyCode": "EUR",
        "status": "COMPLETED",
        "type": "PURCHASE",
        "timeCreated": created,
        "merchant": {"name": "Rewe", "category": "RETAIL_STORES"},
        "cardLastFour": "7164",
    }
    base.update(overrides)
    return base


class TestIterTransactions:
    @staticmethod
    def _page(items: list[dict[str, object]]) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = items
        resp.raise_for_status.return_value = None
        return resp

    def test_pagination_stops_at_start_boundary(self) -> None:
        client = CardsClient(cookie_header=SESSION_COOKIE)
        page1 = [
            _tx(3, "2025-12-02T10:00:00Z"),
            _tx(2, "2025-11-02T10:00:00Z"),
            _tx(1, "2025-10-02T10:00:00Z"),
        ]
        page2 = [
            _tx(0, "2025-09-30T23:59:59Z"),  # older than start -> stop
        ]
        with (
            patch.object(
                client.client, "get", side_effect=[self._page(page1), self._page(page2)]
            ) as mocked,
            patch.object(time, "sleep"),
        ):
            start = datetime(2025, 10, 1, tzinfo=UTC)
            end = datetime(2026, 1, 1, tzinfo=UTC)
            result = list(client.iter_transactions(start, end))
        assert [tx.id for tx in result] == [3, 2, 1]
        assert mocked.call_count == 2

    def test_items_newer_than_end_are_skipped(self) -> None:
        client = CardsClient(cookie_header=SESSION_COOKIE)
        page = [
            _tx(5, "2026-02-01T10:00:00Z"),  # after end -> skipped
            _tx(4, "2025-12-01T10:00:00Z"),  # in range
        ]
        # second page empty terminates iteration
        with (
            patch.object(
                client.client, "get", side_effect=[self._page(page), self._page([])]
            ),
            patch.object(time, "sleep"),
        ):
            start = datetime(2025, 1, 1, tzinfo=UTC)
            end = datetime(2026, 1, 1, tzinfo=UTC)
            result = list(client.iter_transactions(start, end))
        assert [tx.id for tx in result] == [4]

    def test_empty_first_page(self) -> None:
        client = CardsClient(cookie_header=SESSION_COOKIE)
        with patch.object(client.client, "get", return_value=self._page([])):
            result = list(
                client.iter_transactions(
                    datetime(2025, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)
                )
            )
        assert result == []

    def test_out_of_order_page_aborts(self) -> None:
        client = CardsClient(cookie_header=SESSION_COOKIE)
        page = [
            _tx(1, "2025-11-02T10:00:00Z"),
            _tx(2, "2025-12-02T10:00:00Z"),  # newer than previous -> violates ordering
        ]
        with patch.object(client.client, "get", return_value=self._page(page)):
            with pytest.raises(RuntimeError, match="out-of-order"):
                list(
                    client.iter_transactions(
                        datetime(2025, 1, 1, tzinfo=UTC),
                        datetime(2026, 1, 1, tzinfo=UTC),
                    )
                )
