from t212_cli.tax.models import EtfProfile, EtfHolding
from typing import Generator
import os
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from t212_cli.cli.main import app

runner = CliRunner()


@pytest.fixture
def mock_env() -> Generator[None, None, None]:
    with patch.dict(os.environ, {"T212_API_KEY_ID": "test", "T212_SECRET_KEY": "test"}):
        yield


@pytest.fixture
def mock_client() -> Generator[MagicMock, None, None]:
    with patch("t212_cli.cli.main.get_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


SAMPLE_PROFILE = EtfProfile(
    isin="IE00BJ0KDQ92",
    name="Xtrackers MSCI World UCITS ETF 1C",
    ter=0.0012,
    fund_size_eur=19862.0,
    distribution_policy="Accumulating",
    replication="Physical",
    fund_currency="USD",
    holdings=[
        EtfHolding(name="NVIDIA Corp.", isin="US67066G1040", weight=0.0544),
        EtfHolding(name="Apple", isin="US0378331005", weight=0.049),
    ],
    countries={"United States": 0.6791, "Japan": 0.0559},
    sectors={"Technology": 0.3064, "Financials": 0.1398},
    asset_classes={"cash": 0.0032, "stock": 0.9964},
)


@patch("t212_cli.cli.main.scrape_justetf")
def test_etf_profile(
    mock_scrape: MagicMock, mock_env: None, mock_client: MagicMock
) -> None:
    mock_scrape.return_value = SAMPLE_PROFILE.model_copy()
    mock_client.get_instruments.return_value = []

    result = runner.invoke(app, ["etf", "profile", "IE00BJ0KDQ92"])
    assert result.exit_code == 0
    assert "Xtrackers" in result.stdout
    assert "NVIDIA" in result.stdout


@patch("t212_cli.cli.main.scrape_justetf")
def test_etf_profile_not_found(
    mock_scrape: MagicMock, mock_env: None, mock_client: MagicMock
) -> None:
    mock_scrape.return_value = None

    result = runner.invoke(app, ["etf", "profile", "MISSING"])
    assert result.exit_code == 0
    assert "Could not fetch" in result.stdout


@patch("t212_cli.cli.main.scrape_justetf")
def test_etf_holdings(
    mock_scrape: MagicMock, mock_env: None, mock_client: MagicMock
) -> None:
    mock_scrape.return_value = SAMPLE_PROFILE.model_copy()

    result = runner.invoke(app, ["etf", "holdings", "IE00BJ0KDQ92"])
    assert result.exit_code == 0
    assert "NVIDIA" in result.stdout
    assert "Apple" in result.stdout


@patch("t212_cli.cli.main.scrape_justetf")
def test_etf_holdings_empty(
    mock_scrape: MagicMock, mock_env: None, mock_client: MagicMock
) -> None:
    mock_scrape.return_value = EtfProfile(isin="TEST")
    mock_client.get_instruments.return_value = []

    result = runner.invoke(app, ["etf", "holdings", "TEST"])
    assert result.exit_code == 0
    assert "No holdings" in result.stdout


@patch("t212_cli.cli.main.scrape_justetf")
def test_etf_regions(
    mock_scrape: MagicMock, mock_env: None, mock_client: MagicMock
) -> None:
    mock_scrape.return_value = SAMPLE_PROFILE.model_copy()

    result = runner.invoke(app, ["etf", "regions", "IE00BJ0KDQ92"])
    assert result.exit_code == 0
    assert "United States" in result.stdout
    assert "Japan" in result.stdout


@patch("t212_cli.cli.main.scrape_justetf")
def test_etf_regions_empty(
    mock_scrape: MagicMock, mock_env: None, mock_client: MagicMock
) -> None:
    mock_scrape.return_value = EtfProfile(isin="TEST")

    result = runner.invoke(app, ["etf", "regions", "TEST"])
    assert result.exit_code == 0
    assert "No country" in result.stdout


@patch("t212_cli.cli.main.scrape_justetf")
def test_etf_sectors(
    mock_scrape: MagicMock, mock_env: None, mock_client: MagicMock
) -> None:
    mock_scrape.return_value = SAMPLE_PROFILE.model_copy()

    result = runner.invoke(app, ["etf", "sectors", "IE00BJ0KDQ92"])
    assert result.exit_code == 0
    assert "Technology" in result.stdout
    assert "Financials" in result.stdout


@patch("t212_cli.cli.main.scrape_justetf")
def test_etf_sectors_empty(
    mock_scrape: MagicMock, mock_env: None, mock_client: MagicMock
) -> None:
    mock_scrape.return_value = EtfProfile(isin="TEST")
    mock_client.get_instruments.return_value = []

    result = runner.invoke(app, ["etf", "sectors", "TEST"])
    assert result.exit_code == 0
    assert "No sector" in result.stdout
