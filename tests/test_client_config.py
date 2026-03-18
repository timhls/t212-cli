import os
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from t212_cli.cli.main import app
from t212_cli.client.base import Trading212Client


def test_client_default_url() -> None:
    client = Trading212Client(api_key_id="test", secret_key="test")
    assert client.base_url == Trading212Client.DEMO_URL


def test_client_live_url() -> None:
    client = Trading212Client(
        api_key_id="test", secret_key="test", base_url=Trading212Client.LIVE_URL
    )
    assert client.base_url == Trading212Client.LIVE_URL


runner = CliRunner()


@patch.dict(os.environ, {"T212_API_KEY_ID": "test", "T212_SECRET_KEY": "test"})
@patch("t212_cli.cli.main.Trading212Client")
def test_cli_default_is_demo(mock_client: MagicMock) -> None:
    mock_client.DEMO_URL = "https://demo.trading212.com/api/v0"
    mock_client.LIVE_URL = "https://live.trading212.com/api/v0"
    # We need to invoke a command that calls get_client()
    # "account summary" is a good candidate
    with patch("t212_cli.client.base.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"id": 123, "currencyCode": "EUR"}
        runner.invoke(app, ["account", "summary"])

        # Check if Trading212Client was instantiated with DEMO_URL
        mock_client.assert_called()
        _, kwargs = mock_client.call_args
        assert kwargs["base_url"] == "https://demo.trading212.com/api/v0"


@patch.dict(os.environ, {"T212_API_KEY_ID": "test", "T212_SECRET_KEY": "test"})
@patch("t212_cli.cli.main.Trading212Client")
def test_cli_live_flag(mock_client: MagicMock) -> None:
    mock_client.DEMO_URL = "https://demo.trading212.com/api/v0"
    mock_client.LIVE_URL = "https://live.trading212.com/api/v0"
    with patch("t212_cli.client.base.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"id": 123, "currencyCode": "EUR"}
        runner.invoke(app, ["--live", "account", "summary"])

        mock_client.assert_called()
        _, kwargs = mock_client.call_args
        assert kwargs["base_url"] == "https://live.trading212.com/api/v0"
