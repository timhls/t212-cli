from t212_cli.tax.justetf import scrape_justetf
from t212_cli.tax.models import EtfProfile, EtfHolding
from unittest.mock import patch, MagicMock


JUSTETF_HTML = """
<html><body>
<h1>Xtrackers MSCI World UCITS ETF 1C | A1XB5U | IE00BJ0KDQ92 | XDWD</h1>
<div>
  <h3>Top 10 Holdings</h3>
  <div>
    <a href="/stock-profiles/US67066G1040">NVIDIA Corp.</a> 5.44%
    <a href="/stock-profiles/US0378331005">Apple</a> 4.90%
    <a href="/stock-profiles/US5949181045">Microsoft</a> 3.00%
  </div>
</div>
<div>
  <h3>Countries</h3>
  <table class="table mb-0">
    <tr><td>United States</td><td>67.91%</td></tr>
    <tr><td>Japan</td><td>5.59%</td></tr>
    <tr><td>Other</td><td>20.54%</td></tr>
  </table>
</div>
<div>
  <h3>Sectors</h3>
  <table class="table mb-0">
    <tr><td>Technology</td><td>30.64%</td></tr>
    <tr><td>Financials</td><td>13.98%</td></tr>
    <tr><td>Other</td><td>35.99%</td></tr>
  </table>
</div>
<table>
  <tr data-testid="etf-basics_row_ter">
    <td class="vallabel" data-testid="etf-basics_label_ter">Total expense ratio</td>
    <td><div class="val" data-testid="tl_etf-basics_value_ter">0.12% p.a.</div></td>
  </tr>
  <tr data-testid="etf-basics_row_fund-size">
    <td class="vallabel" data-testid="etf-basics_label_fund-size">Fund size</td>
    <td>EUR 19,862m <span class="indicator-3 indicator-3--green ml-2"></span></td>
  </tr>
  <tr data-testid="etf-basics_row_distribution-policy">
    <td class="vallabel" data-testid="etf-basics_label_distribution-policy">Distribution policy</td>
    <td data-testid="tl_etf-basics_value_distribution-policy">Accumulating</td>
  </tr>
  <tr data-testid="etf-basics_row_fund-currency">
    <td class="vallabel" data-testid="etf-basics_label_fund-currency">Fund currency</td>
    <td data-testid="tl_etf-basics_value_fund-currency">USD</td>
  </tr>
  <tr data-testid="etf-basics_row_replication">
    <td class="vallabel" data-testid="etf-basics_label_replication">Replication</td>
    <td><span data-testid="tl_etf-basics_value_replication">Physical</span><span data-testid="tl_etf-basics_value_replication-method">(Optimized sampling)</span></td>
  </tr>
</table>
</body></html>
"""

JUSTETF_HTML_MINIMAL = """
<html><body>
<h1>WisdomTree Agriculture</h1>
</body></html>
"""


@patch("t212_cli.tax.justetf.requests.get")
def test_scrape_justetf_full(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = JUSTETF_HTML
    mock_get.return_value = mock_response

    profile = scrape_justetf("IE00BJ0KDQ92")
    assert profile is not None
    assert isinstance(profile, EtfProfile)
    assert profile.isin == "IE00BJ0KDQ92"
    assert profile.name is not None
    assert "Xtrackers" in profile.name

    assert profile.ter == 0.0012
    assert profile.fund_size_eur == 19862.0
    assert profile.distribution_policy == "Accumulating"
    assert profile.fund_currency == "USD"
    assert "Physical" in (profile.replication or "")

    assert len(profile.holdings) == 3
    assert isinstance(profile.holdings[0], EtfHolding)
    assert profile.holdings[0].name == "NVIDIA Corp."
    assert profile.holdings[0].isin == "US67066G1040"
    assert abs(profile.holdings[0].weight - 0.0544) < 1e-10

    assert "United States" in profile.countries
    assert abs(profile.countries["United States"] - 0.6791) < 1e-10
    assert abs(profile.countries["Japan"] - 0.0559) < 1e-10

    assert "Technology" in profile.sectors
    assert abs(profile.sectors["Technology"] - 0.3064) < 1e-10


@patch("t212_cli.tax.justetf.requests.get")
def test_scrape_justetf_minimal(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = JUSTETF_HTML_MINIMAL
    mock_get.return_value = mock_response

    profile = scrape_justetf("GB00B15KYH63")
    assert profile is not None
    assert profile.isin == "GB00B15KYH63"
    assert len(profile.holdings) == 0
    assert len(profile.countries) == 0
    assert len(profile.sectors) == 0


@patch("t212_cli.tax.justetf.requests.get")
def test_scrape_justetf_not_found(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    profile = scrape_justetf("MISSING")
    assert profile is None


@patch("t212_cli.tax.justetf.requests.get")
def test_scrape_justetf_error(mock_get: MagicMock) -> None:
    from curl_cffi import requests

    mock_get.side_effect = requests.RequestsError("Network error")

    profile = scrape_justetf("ERR")
    assert profile is None
