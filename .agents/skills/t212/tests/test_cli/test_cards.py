import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from t212_cli.cli.cards import app
from t212_cli.client.cards import CardSessionExpiredError
from t212_cli.models.cards import CardTransaction
from typer.testing import CliRunner

runner = CliRunner()

COOKIE_ENV = {"T212_CARDS_COOKIES": "TRADING212_SESSION_LIVE=abc123"}


def _tx(tx_id: int, created: str, amount: float = 10.0) -> CardTransaction:
    kwargs: dict[str, Any] = {
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
    return CardTransaction(**kwargs)


def _mock_client(transactions: list[CardTransaction]) -> MagicMock:
    client = MagicMock()
    client.iter_transactions.return_value = iter(transactions)
    return client


def test_help_lists_transactions() -> None:
    # NO_COLOR + wide COLUMNS keeps rich output plain and unwrapped in CI
    result = runner.invoke(
        app,
        ["transactions", "--help"],
        env={"NO_COLOR": "1", "COLUMNS": "200"},
    )
    assert result.exit_code == 0
    assert "--from" in result.stdout
    assert "--cookie-file" in result.stdout


def test_missing_cookies_errors_cleanly() -> None:
    result = runner.invoke(app, ["transactions", "--from", "2025-01-01"])
    assert result.exit_code == 1
    assert "session cookies" in result.stdout


def test_invalid_format_errors() -> None:
    result = runner.invoke(
        app,
        ["transactions", "--from", "2025-01-01", "--format", "xml"],
        env=COOKIE_ENV,
    )
    assert result.exit_code == 1
    assert "json, md, csv" in result.stdout


def test_invalid_timezone_errors() -> None:
    result = runner.invoke(
        app,
        ["transactions", "--from", "2025-01-01", "--tz", "Mars/Olympus"],
        env=COOKIE_ENV,
    )
    assert result.exit_code == 1
    assert "unknown timezone" in result.stdout


def test_from_after_to_errors() -> None:
    result = runner.invoke(
        app,
        ["transactions", "--from", "2025-12-31", "--to", "2025-01-01"],
        env=COOKIE_ENV,
    )
    assert result.exit_code == 1
    assert "before" in result.stdout


def test_json_output() -> None:
    client = _mock_client([_tx(1, "2025-12-01T10:00:00Z", amount=12.34)])
    with (
        patch("t212_cli.cli.cards.CardsClient", return_value=client) as ctor,
    ):
        result = runner.invoke(
            app,
            ["transactions", "--from", "2025-01-01", "--to", "2025-12-31"],
            env=COOKIE_ENV,
        )
    assert result.exit_code == 0
    ctor.assert_called_once_with(cookie_header="TRADING212_SESSION_LIVE=abc123")
    data = json.loads(result.stdout)
    assert data[0]["id"] == 1
    assert data[0]["billingAmount"] == 12.34
    # Period boundaries: Berlin midnights converted to UTC
    kwargs = client.iter_transactions.call_args
    start, end = kwargs.args
    assert start == datetime(2024, 12, 31, 23, 0, tzinfo=timezone.utc)
    assert end == datetime(2025, 12, 31, 23, 0, tzinfo=timezone.utc)


def test_json_output_custom_timezone_boundaries() -> None:
    client = _mock_client([])
    with patch("t212_cli.cli.cards.CardsClient", return_value=client):
        result = runner.invoke(
            app,
            [
                "transactions",
                "--from",
                "2025-06-01",
                "--to",
                "2025-06-30",
                "--tz",
                "UTC",
            ],
            env=COOKIE_ENV,
        )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == []
    start, end = client.iter_transactions.call_args.args
    assert start == datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2025, 7, 1, 0, 0, tzinfo=timezone.utc)


def test_markdown_output() -> None:
    client = _mock_client([_tx(1, "2025-12-01T10:00:00Z", amount=12.34)])
    with patch("t212_cli.cli.cards.CardsClient", return_value=client):
        result = runner.invoke(
            app,
            [
                "transactions",
                "--from",
                "2025-01-01",
                "--to",
                "2025-12-31",
                "--format",
                "md",
            ],
            env=COOKIE_ENV,
        )
    assert result.exit_code == 0
    assert "# Trading 212 — Card Transactions" in result.stdout
    assert "| -12.34 |" in result.stdout


def test_csv_output() -> None:
    client = _mock_client([_tx(1, "2025-12-01T10:00:00Z", amount=12.34)])
    with patch("t212_cli.cli.cards.CardsClient", return_value=client):
        result = runner.invoke(
            app,
            ["transactions", "--from", "2025-12-01", "--format", "csv"],
            env=COOKIE_ENV,
        )
    assert result.exit_code == 0
    lines = result.stdout.strip().splitlines()
    assert lines[0].startswith("transaction_id")
    assert ",1," in lines[1]
    assert "Rewe" in lines[1]


def test_session_expired_errors_cleanly() -> None:
    client = MagicMock()
    client.iter_transactions.side_effect = CardSessionExpiredError(
        "Cards API returned 401"
    )
    with patch("t212_cli.cli.cards.CardsClient", return_value=client):
        result = runner.invoke(
            app,
            ["transactions", "--from", "2025-01-01"],
            env=COOKIE_ENV,
        )
    assert result.exit_code == 1
    assert "Cards API returned 401" in result.stdout


def test_generic_fetch_error_errors_cleanly() -> None:
    client = MagicMock()
    client.iter_transactions.side_effect = RuntimeError("boom")
    with patch("t212_cli.cli.cards.CardsClient", return_value=client):
        result = runner.invoke(
            app,
            ["transactions", "--from", "2025-01-01"],
            env=COOKIE_ENV,
        )
    assert result.exit_code == 1
    assert "boom" in result.stdout


def test_bad_from_format_errors() -> None:
    result = runner.invoke(
        app,
        ["transactions", "--from", "01.01.2025"],
        env=COOKIE_ENV,
    )
    assert result.exit_code != 0
