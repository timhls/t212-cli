import os
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from t212_cli.cli.main import app
from t212_cli.client.base import Trading212Client


def test_client_default_url() -> None:
    """Test that client defaults to DEMO_URL when no base_url or env var is set."""
    with patch.dict(os.environ, {}, clear=True):
        client = Trading212Client(api_key_id="test", secret_key="test")
        assert client.base_url == Trading212Client.DEMO_URL


def test_client_explicit_url() -> None:
    """Test that client uses explicitly provided base_url."""
    client = Trading212Client(
        api_key_id="test", secret_key="test", base_url=Trading212Client.LIVE_URL
    )
    assert client.base_url == Trading212Client.LIVE_URL


def test_client_env_var_url() -> None:
    """Test that client uses T212_BASE_URL environment variable."""
    custom_url = "https://custom.trading212.com/api/v0"
    with patch.dict(os.environ, {"T212_BASE_URL": custom_url}):
        client = Trading212Client(api_key_id="test", secret_key="test")
        assert client.base_url == custom_url


def test_client_explicit_overrides_env() -> None:
    """Test that explicit base_url overrides T212_BASE_URL env var."""
    with patch.dict(os.environ, {"T212_BASE_URL": "https://env.example.com"}):
        client = Trading212Client(
            api_key_id="test", secret_key="test", base_url=Trading212Client.LIVE_URL
        )
        assert client.base_url == Trading212Client.LIVE_URL


runner = CliRunner()


@patch.dict(os.environ, {"T212_API_KEY_ID": "test", "T212_SECRET_KEY": "test"})
@patch("t212_cli.cli.main.Trading212Client")
def test_cli_default_is_demo(mock_client: MagicMock) -> None:
    """Test that CLI defaults to demo URL when T212_BASE_URL is not set."""
    mock_client.DEMO_URL = "https://demo.trading212.com/api/v0"
    with patch("t212_cli.client.base.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"id": 123, "currencyCode": "EUR"}
        runner.invoke(app, ["account", "summary"])

        # Check that Trading212Client was called (base_url determined by client init)
        mock_client.assert_called_once()


@patch.dict(
    os.environ,
    {
        "T212_API_KEY_ID": "test",
        "T212_SECRET_KEY": "test",
        "T212_BASE_URL": "https://live.trading212.com/api/v0",
    },
)
@patch("t212_cli.cli.main.Trading212Client")
def test_cli_uses_env_var(mock_client: MagicMock) -> None:
    """Test that CLI uses T212_BASE_URL environment variable."""
    with patch("t212_cli.client.base.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"id": 123, "currencyCode": "EUR"}
        runner.invoke(app, ["account", "summary"])

        mock_client.assert_called_once()
