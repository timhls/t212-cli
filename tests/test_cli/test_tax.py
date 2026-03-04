import datetime
import os
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from t212_cli.cli.main import app
from t212_cli.models import (
    Fill,
    FillWalletImpact,
    HistoricalOrder,
    InitiatedFrom,
    Instrument,
    Order,
    Side,
    Status1,
    Strategy,
    Tax,
    Type3,
)
from t212_cli.tax.models import AssetClass, TaxConfig, TaxInstrument


runner = CliRunner()


@patch("t212_cli.cli.tax.load_tax_config")
def test_tax_config_empty(mock_load: MagicMock) -> None:
    mock_load.return_value = TaxConfig()
    result = runner.invoke(app, ["tax", "config"])
    assert result.exit_code == 0
    assert "No tax configurations saved yet" in result.stdout


@patch("t212_cli.cli.tax.load_tax_config")
def test_tax_config_existing(mock_load: MagicMock) -> None:
    config = TaxConfig(
        instruments={"IE00B4L5Y983": TaxInstrument(asset_class=AssetClass.AKTIENFONDS)}
    )
    mock_load.return_value = config
    result = runner.invoke(app, ["tax", "config"])
    assert result.exit_code == 0
    assert "IE00B4L5Y983" in result.stdout
    assert "Aktienfonds" in result.stdout


@patch("t212_cli.cli.tax.get_instrument_config")
def test_tax_classify_existing(mock_get: MagicMock) -> None:
    mock_get.return_value = TaxInstrument(asset_class=AssetClass.AKTIEN)
    result = runner.invoke(app, ["tax", "classify", "US1234"])
    assert result.exit_code == 0
    assert "already configured locally" in result.stdout


@patch("t212_cli.cli.tax.get_instrument_config")
@patch("t212_cli.cli.tax.scrape_finanzfluss")
@patch("t212_cli.cli.tax.update_instrument_config")
def test_tax_classify_scrape_success(
    mock_update: MagicMock, mock_scrape: MagicMock, mock_get: MagicMock
) -> None:
    mock_get.return_value = None
    mock_scrape.return_value = TaxInstrument(asset_class=AssetClass.AKTIENFONDS)
    result = runner.invoke(app, ["tax", "classify", "IE1234"])

    assert result.exit_code == 0
    assert "Successfully detected tax profile" in result.stdout
    mock_update.assert_called_once()


@patch("t212_cli.cli.tax.get_instrument_config")
@patch("t212_cli.cli.tax.scrape_finanzfluss")
def test_tax_classify_scrape_fail(mock_scrape: MagicMock, mock_get: MagicMock) -> None:
    mock_get.return_value = None
    mock_scrape.return_value = None
    result = runner.invoke(app, ["tax", "classify", "MISSING"])

    assert result.exit_code == 0
    assert "Could not auto-detect" in result.stdout


@patch.dict(os.environ, {"T212_API_KEY_ID": "", "T212_SECRET_KEY": ""})
def test_tax_report_missing_creds() -> None:
    result = runner.invoke(app, ["tax", "fifo-report"])
    assert result.exit_code == 1
    assert "Error: Both T212_API_KEY_ID" in result.stdout


@patch("t212_cli.cli.tax.get_client")
@patch("t212_cli.cli.tax.FifoEngine")
def test_tax_report_success(
    mock_engine_cls: MagicMock, mock_get_client: MagicMock
) -> None:
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Create mock orders
    dt = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    mock_order = HistoricalOrder(
        order=Order(
            id=1,
            ticker="US123",
            side=Side.BUY,
            createdAt=dt,
            quantity=10.0,
            status=Status1.FILLED,
            type=Type3.MARKET,
            instrument=Instrument(
                ticker="US123", isin="US123", currency="USD", name="Test"
            ),
            currency="USD",
            extendedHours=False,
            filledQuantity=10.0,
            filledValue=1000.0,
            initiatedFrom=InitiatedFrom.API,
            limitPrice=None,
            stopPrice=None,
            strategy=Strategy.QUANTITY,
            value=1000.0,
        ),
        fill=Fill(
            filledAt=dt,
            quantity=10.0,
            price=100.0,
            walletImpact=FillWalletImpact(taxes=[Tax(quantity=2.0)]),
        ),
    )

    mock_res = MagicMock()
    mock_res.items = [mock_order]
    mock_res.nextPagePath = None
    mock_client.get_historical_orders.return_value = mock_res

    mock_engine = MagicMock()
    mock_engine.year_taxable_gains = 500.0
    mock_engine.year_aktien_verlust_generated = 10.0
    mock_engine.year_sonstige_verlust_generated = 20.0
    mock_engine.aktien_verlusttopf = 0.0
    mock_engine.sonstige_verlusttopf = 0.0
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(app, ["tax", "fifo-report", "--year", "2024"])

    # Assert
    assert result.exit_code == 0, f"Stdout: {result.stdout}, Exc: {result.exception}"
    assert "Loaded 1 historical orders" in result.stdout
    assert "Tax Report 2024" in result.stdout
    assert "500.00" in result.stdout


@patch("t212_cli.cli.tax.update_instrument_config")
@patch("t212_cli.cli.tax.get_instrument_config")
@patch("t212_cli.cli.tax.get_client")
@patch("t212_cli.cli.tax.scrape_finanzfluss")
def test_tax_report_auto_classify_fallback(
    mock_scrape: MagicMock,
    mock_get_client: MagicMock,
    mock_get_config: MagicMock,
    mock_update: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Ensure config says it's missing, forcing a scrape
    mock_get_config.return_value = None

    dt = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    mock_order = HistoricalOrder(
        order=Order(
            id=2,
            ticker="MISSING_ISIN",
            side=Side.BUY,
            createdAt=dt,
            quantity=1.0,
            status=Status1.FILLED,
            type=Type3.MARKET,
            instrument=Instrument(
                ticker="MISSING_ISIN",
                isin="MISSING_ISIN",
                currency="USD",
                name="Test Missing",
            ),
            currency="USD",
            extendedHours=False,
            filledQuantity=1.0,
            filledValue=10.0,
            initiatedFrom=InitiatedFrom.API,
            limitPrice=None,
            stopPrice=None,
            strategy=Strategy.QUANTITY,
            value=10.0,
        ),
        fill=Fill(
            filledAt=dt,
            quantity=1.0,
            price=10.0,
            walletImpact=FillWalletImpact(fxRate=1.1),
        ),
    )

    mock_res = MagicMock()
    mock_res.items = [mock_order]
    mock_res.nextPagePath = None
    mock_client.get_historical_orders.return_value = mock_res

    mock_scrape.return_value = TaxInstrument(asset_class=AssetClass.AKTIENFONDS)

    result = runner.invoke(app, ["tax", "fifo-report", "--year", "2024"])

    assert result.exit_code == 0
    mock_scrape.assert_called_once_with("MISSING_ISIN")
    mock_update.assert_called_once()


@patch("t212_cli.cli.tax.get_client")
def test_tax_report_pagination(mock_get_client: MagicMock) -> None:
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    dt = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    mock_order = HistoricalOrder(
        order=Order(
            id=3,
            ticker="US123",
            instrument=Instrument(
                ticker="US123", isin="US123", currency="USD", name="Test"
            ),
            side=Side.BUY,
            createdAt=dt,
            quantity=1.0,
            status=Status1.FILLED,
            type=Type3.MARKET,
            currency="USD",
            extendedHours=False,
            filledQuantity=1.0,
            filledValue=10.0,
            initiatedFrom=InitiatedFrom.API,
            limitPrice=None,
            stopPrice=None,
            strategy=Strategy.QUANTITY,
            value=10.0,
        ),
        fill=Fill(filledAt=dt, quantity=1.0, price=10.0),
    )

    # Setup mocked responses for pagination
    mock_res1 = MagicMock()
    mock_res1.items = [mock_order]
    mock_res1.nextPagePath = "/api/v0/equity/history/orders?cursor=123"

    mock_res2 = MagicMock()
    mock_res2.items = [mock_order]
    mock_res2.nextPagePath = None

    mock_client.get_historical_orders.side_effect = [mock_res1, mock_res2]

    result = runner.invoke(app, ["tax", "fifo-report", "--year", "2024"])
    assert result.exit_code == 0
    assert "Loaded 2 historical orders" in result.stdout
