from t212_cli.tax.config import (
    load_tax_config,
    save_tax_config,
    get_instrument_config,
    update_instrument_config,
)
from t212_cli.tax.models import TaxConfig, TaxInstrument, AssetClass
from unittest.mock import mock_open, patch, MagicMock


@patch("pathlib.Path.exists", return_value=False)
def test_load_tax_config_missing(mock_exists: MagicMock) -> None:
    config = load_tax_config()
    assert isinstance(config, TaxConfig)
    assert len(config.instruments) == 0


@patch("pathlib.Path.exists", return_value=True)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="instruments:\n  IE123:\n    asset_class: Aktienfonds\n    tfs_quote: 0.3",
)
def test_load_tax_config_existing(mock_file: MagicMock, mock_exists: MagicMock) -> None:
    config = load_tax_config()
    assert "IE123" in config.instruments
    assert config.instruments["IE123"].asset_class == AssetClass.AKTIENFONDS
    assert config.instruments["IE123"].tfs_quote == 0.3


@patch("pathlib.Path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="invalid_yaml: {")
def test_load_tax_config_invalid(mock_file: MagicMock, mock_exists: MagicMock) -> None:
    config = load_tax_config()
    assert isinstance(config, TaxConfig)
    assert len(config.instruments) == 0


@patch("t212_cli.tax.config.CONFIG_DIR")
@patch("builtins.open", new_callable=mock_open)
def test_save_tax_config(mock_file: MagicMock, mock_dir: MagicMock) -> None:
    config = TaxConfig()
    save_tax_config(config)
    mock_file.assert_called_once()
    mock_dir.mkdir.assert_called_with(parents=True, exist_ok=True)


@patch("t212_cli.tax.config.load_tax_config")
def test_get_instrument_config(mock_load: MagicMock) -> None:
    mock_load.return_value = TaxConfig(
        instruments={"TEST": TaxInstrument(asset_class=AssetClass.AKTIEN)}
    )
    assert get_instrument_config("TEST") is not None
    assert get_instrument_config("MISSING") is None


@patch("t212_cli.tax.config.save_tax_config")
@patch("t212_cli.tax.config.load_tax_config")
def test_update_instrument_config(mock_load: MagicMock, mock_save: MagicMock) -> None:
    mock_load.return_value = TaxConfig()
    instr = TaxInstrument(asset_class=AssetClass.BOND)
    update_instrument_config("NEW_ISIN", instr)

    mock_save.assert_called_once()
    saved_config = mock_save.call_args[0][0]
    assert "NEW_ISIN" in saved_config.instruments
