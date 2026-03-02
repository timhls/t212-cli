import os
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from t212_cli.cli.main import app

runner = CliRunner()


@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {"T212_API_KEY_ID": "test", "T212_SECRET_KEY": "test"}):
        yield


@pytest.fixture
def mock_client():
    with patch("t212_cli.cli.main.get_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


def test_missing_env_vars():
    with patch.dict(os.environ, clear=True):
        result = runner.invoke(app, ["account", "summary"])
        assert result.exit_code == 1
        assert "Error:" in result.stdout


def test_account_summary(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": "1"}'
    mock_client.get_account_summary.return_value = mock_model

    result = runner.invoke(app, ["account", "summary"])
    assert result.exit_code == 0
    assert "1" in result.stdout


def test_account_summary_error(mock_env, mock_client):
    mock_client.get_account_summary.side_effect = Exception("API Error")
    result = runner.invoke(app, ["account", "summary"])
    assert result.exit_code == 0
    assert "Error fetching account summary" in result.stdout


def test_positions_list(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump.return_value = {"ticker": "AAPL"}
    mock_client.get_positions.return_value = [mock_model]

    result = runner.invoke(app, ["positions", "list", "--ticker", "AAPL"])
    assert result.exit_code == 0
    assert "AAPL" in result.stdout


def test_positions_list_error(mock_env, mock_client):
    mock_client.get_positions.side_effect = Exception("API Error")
    result = runner.invoke(app, ["positions", "list"])
    assert result.exit_code == 0
    assert "Error fetching positions" in result.stdout


def test_history_dividends(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"items": []}'
    mock_client.get_historical_dividends.return_value = mock_model

    result = runner.invoke(app, ["history", "dividends"])
    assert result.exit_code == 0
    assert "items" in result.stdout


def test_history_dividends_error(mock_env, mock_client):
    mock_client.get_historical_dividends.side_effect = Exception("API Error")
    result = runner.invoke(app, ["history", "dividends"])
    assert result.exit_code == 0
    assert "Error" in result.stdout


def test_history_orders(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"items": []}'
    mock_client.get_historical_orders.return_value = mock_model

    result = runner.invoke(app, ["history", "orders"])
    assert result.exit_code == 0


def test_history_orders_error(mock_env, mock_client):
    mock_client.get_historical_orders.side_effect = Exception("API Error")
    result = runner.invoke(app, ["history", "orders"])
    assert result.exit_code == 0


def test_history_transactions(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"items": []}'
    mock_client.get_historical_transactions.return_value = mock_model

    result = runner.invoke(app, ["history", "transactions"])
    assert result.exit_code == 0


def test_history_transactions_error(mock_env, mock_client):
    mock_client.get_historical_transactions.side_effect = Exception("API Error")
    result = runner.invoke(app, ["history", "transactions"])
    assert result.exit_code == 0


def test_metadata_exchanges(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump.return_value = {"id": 1}
    mock_client.get_exchanges.return_value = [mock_model]

    result = runner.invoke(app, ["metadata", "exchanges"])
    assert result.exit_code == 0


def test_metadata_exchanges_error(mock_env, mock_client):
    mock_client.get_exchanges.side_effect = Exception("API Error")
    result = runner.invoke(app, ["metadata", "exchanges"])
    assert result.exit_code == 0


def test_metadata_instruments(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump.return_value = {"ticker": "AAPL"}
    mock_client.get_instruments.return_value = [mock_model]

    result = runner.invoke(app, ["metadata", "instruments"])
    assert result.exit_code == 0


def test_metadata_instruments_error(mock_env, mock_client):
    mock_client.get_instruments.side_effect = Exception("API Error")
    result = runner.invoke(app, ["metadata", "instruments"])
    assert result.exit_code == 0


def test_orders_list(mock_env, mock_client):
    mock_client.get_orders.return_value = []
    result = runner.invoke(app, ["orders", "list"])
    assert result.exit_code == 0


def test_orders_list_error(mock_env, mock_client):
    mock_client.get_orders.side_effect = Exception("API Error")
    result = runner.invoke(app, ["orders", "list"])
    assert result.exit_code == 0


def test_orders_get(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": 1}'
    mock_client.get_order_by_id.return_value = mock_model

    result = runner.invoke(app, ["orders", "get", "1"])
    assert result.exit_code == 0


def test_orders_get_error(mock_env, mock_client):
    mock_client.get_order_by_id.side_effect = Exception("API Error")
    result = runner.invoke(app, ["orders", "get", "1"])
    assert result.exit_code == 0


def test_orders_cancel(mock_env, mock_client):
    mock_client.cancel_order.return_value = None
    result = runner.invoke(app, ["orders", "cancel", "1"])
    assert result.exit_code == 0


def test_orders_cancel_error(mock_env, mock_client):
    mock_client.cancel_order.side_effect = Exception("API Error")
    result = runner.invoke(app, ["orders", "cancel", "1"])
    assert result.exit_code == 0


def test_orders_market(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": 1}'
    mock_client.place_market_order.return_value = mock_model

    result = runner.invoke(app, ["orders", "market", "AAPL", "1.0"])
    assert result.exit_code == 0


def test_orders_market_error(mock_env, mock_client):
    mock_client.place_market_order.side_effect = Exception("API Error")
    result = runner.invoke(app, ["orders", "market", "AAPL", "1.0"])
    assert result.exit_code == 0


def test_pies_list(mock_env, mock_client):
    mock_client.get_pies.return_value = []
    result = runner.invoke(app, ["pies", "list"])
    assert result.exit_code == 0


def test_pies_list_error(mock_env, mock_client):
    mock_client.get_pies.side_effect = Exception("API Error")
    result = runner.invoke(app, ["pies", "list"])
    assert result.exit_code == 0


def test_pies_get(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": 1}'
    mock_client.get_pie_by_id.return_value = mock_model

    result = runner.invoke(app, ["pies", "get", "1"])
    assert result.exit_code == 0


def test_pies_get_error(mock_env, mock_client):
    mock_client.get_pie_by_id.side_effect = Exception("API Error")
    result = runner.invoke(app, ["pies", "get", "1"])
    assert result.exit_code == 0


def test_pies_delete(mock_env, mock_client):
    mock_client.delete_pie.return_value = None
    result = runner.invoke(app, ["pies", "delete", "1"])
    assert result.exit_code == 0


def test_pies_delete_error(mock_env, mock_client):
    mock_client.delete_pie.side_effect = Exception("API Error")
    result = runner.invoke(app, ["pies", "delete", "1"])
    assert result.exit_code == 0


def test_pies_create_json(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": 1}'
    mock_client.create_pie.return_value = mock_model

    payload = '{"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"}'
    result = runner.invoke(app, ["pies", "create", payload])
    assert result.exit_code == 0


def test_pies_create_file(mock_env, mock_client, tmp_path):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": 1}'
    mock_client.create_pie.return_value = mock_model

    payload_file = tmp_path / "payload.json"
    payload_file.write_text(
        '{"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"}'
    )

    result = runner.invoke(app, ["pies", "create", str(payload_file)])
    assert result.exit_code == 0


def test_pies_create_error(mock_env, mock_client):
    mock_client.create_pie.side_effect = Exception("API Error")
    payload = '{"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"}'
    result = runner.invoke(app, ["pies", "create", payload])
    assert result.exit_code == 0


def test_pies_update_json(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": 1}'
    mock_client.update_pie.return_value = mock_model

    payload = '{"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"}'
    result = runner.invoke(app, ["pies", "update", "1", payload])
    assert result.exit_code == 0


def test_pies_update_file(mock_env, mock_client, tmp_path):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": 1}'
    mock_client.update_pie.return_value = mock_model

    payload_file = tmp_path / "payload.json"
    payload_file.write_text(
        '{"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"}'
    )

    result = runner.invoke(app, ["pies", "update", "1", str(payload_file)])
    assert result.exit_code == 0


def test_pies_update_error(mock_env, mock_client):
    mock_client.update_pie.side_effect = Exception("API Error")
    payload = '{"dividendCashAction": "REINVEST", "icon": "Default", "name": "P1"}'
    result = runner.invoke(app, ["pies", "update", "1", payload])
    assert result.exit_code == 0


def test_pies_duplicate_json(mock_env, mock_client):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": 1}'
    mock_client.duplicate_pie.return_value = mock_model

    payload = '{"icon": "Default", "name": "P1"}'
    result = runner.invoke(app, ["pies", "duplicate", "1", payload])
    assert result.exit_code == 0


def test_pies_duplicate_file(mock_env, mock_client, tmp_path):
    mock_model = MagicMock()
    mock_model.model_dump_json.return_value = '{"id": 1}'
    mock_client.duplicate_pie.return_value = mock_model

    payload_file = tmp_path / "payload.json"
    payload_file.write_text('{"icon": "Default", "name": "P1"}')

    result = runner.invoke(app, ["pies", "duplicate", "1", str(payload_file)])
    assert result.exit_code == 0


def test_pies_duplicate_error(mock_env, mock_client):
    mock_client.duplicate_pie.side_effect = Exception("API Error")
    payload = '{"icon": "Default", "name": "P1"}'
    result = runner.invoke(app, ["pies", "duplicate", "1", payload])
    assert result.exit_code == 0
