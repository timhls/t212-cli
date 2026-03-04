from t212_cli.tax.scraper import scrape_finanzfluss
from t212_cli.tax.models import AssetClass
from unittest.mock import patch, MagicMock


@patch("t212_cli.tax.scraper.requests.get")
def test_scrape_finanzfluss_aktienfonds(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Steuerstatus: 30% Teilfreistellung (Aktienquote ≥ 51%)</body></html>"
    mock_get.return_value = mock_response

    instr = scrape_finanzfluss("IE00B4L5Y983")
    assert instr is not None
    assert instr.asset_class == AssetClass.AKTIENFONDS
    assert instr.tfs_quote == 0.3


@patch("t212_cli.tax.scraper.requests.get")
def test_scrape_finanzfluss_mischfonds(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Steuerstatus: 15% Teilfreistellung</body></html>"
    mock_get.return_value = mock_response

    instr = scrape_finanzfluss("IE00M")
    assert instr is not None
    assert instr.asset_class == AssetClass.MISCHFONDS
    assert instr.tfs_quote == 0.15


@patch("t212_cli.tax.scraper.requests.get")
def test_scrape_finanzfluss_sonstiger(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Steuerstatus: 0% Teilfreistellung</body></html>"
    mock_get.return_value = mock_response

    instr = scrape_finanzfluss("IE00S")
    assert instr is not None
    assert instr.asset_class == AssetClass.SONSTIGER_FONDS
    assert instr.tfs_quote == 0.0


@patch("t212_cli.tax.scraper.requests.get")
def test_scrape_finanzfluss_physical_etc(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Replikation: Physisch... Type: ETC</body></html>"
    mock_get.return_value = mock_response

    instr = scrape_finanzfluss("JE00B")
    assert instr is not None
    assert instr.asset_class == AssetClass.PHYSICAL_ETC
    assert instr.tfs_quote == 0.0


@patch("t212_cli.tax.scraper.requests.get")
def test_scrape_finanzfluss_not_found(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    instr = scrape_finanzfluss("MISSING")
    assert instr is None


@patch("t212_cli.tax.scraper.requests.get")
def test_scrape_finanzfluss_error(mock_get: MagicMock) -> None:
    from curl_cffi import requests

    mock_get.side_effect = requests.RequestsError("Network error")

    instr = scrape_finanzfluss("ERR")
    assert instr is None
