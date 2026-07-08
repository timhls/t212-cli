from unittest.mock import patch, MagicMock


from t212_cli.tax.models import EtfProfile, EtfHolding
from t212_cli.tax.pie_analysis import analyze_pie


SAMPLE_PROFILE_1 = EtfProfile(
    isin="IE00BJ0KDQ92",
    name="MSCI World ETF",
    holdings=[
        EtfHolding(name="NVIDIA Corp.", isin="US67066G1040", weight=0.05),
        EtfHolding(name="Apple", isin="US0378331005", weight=0.04),
    ],
    countries={"United States": 0.68, "Japan": 0.06},
    sectors={"Technology": 0.30, "Financials": 0.14},
)

SAMPLE_PROFILE_2 = EtfProfile(
    isin="IE00BM67HM91",
    name="World Energy ETF",
    holdings=[
        EtfHolding(name="Exxon Mobil", isin="US30231G1022", weight=0.17),
        EtfHolding(name="Apple", isin="US0378331005", weight=0.01),
    ],
    countries={"United States": 0.60, "Canada": 0.16},
    sectors={"Energy": 0.99},
)


def _make_mock_client() -> MagicMock:
    """Create a mock client with pie and instrument resolution."""
    client = MagicMock()

    # Mock pie detail with 2 components
    detail = MagicMock()
    comp1 = MagicMock()
    comp1.ticker = "XDWDd_EQ"
    comp1.currentShare = 0.60
    comp1.expectedShare = 0.60
    comp2 = MagicMock()
    comp2.ticker = "XDW0d_EQ"
    comp2.currentShare = 0.40
    comp2.expectedShare = 0.40
    detail.instruments = [comp1, comp2]
    client.get_pie_by_id.return_value = detail

    # Mock ticker->ISIN resolution
    def resolve_isin(ticker: str) -> str | None:
        return {
            "XDWDd_EQ": "IE00BJ0KDQ92",
            "XDW0d_EQ": "IE00BM67HM91",
        }.get(ticker)

    client.resolve_isin_from_ticker.side_effect = resolve_isin

    return client


@patch("t212_cli.tax.pie_analysis.scrape_justetf")
def test_analyze_pie_basic(mock_scrape: MagicMock) -> None:
    client = _make_mock_client()
    mock_scrape.side_effect = [
        SAMPLE_PROFILE_1.model_copy(),
        SAMPLE_PROFILE_2.model_copy(),
    ]

    result = analyze_pie(client, 12345, enrich_with_yahoo=False)

    assert result.pie_id == 12345
    assert result.total_components == 2
    assert len(result.holdings) == 3  # NVIDIA, Apple (merged), Exxon


@patch("t212_cli.tax.pie_analysis.scrape_justetf")
def test_analyze_pie_merges_duplicate_holdings(mock_scrape: MagicMock) -> None:
    """Apple appears in both ETFs — weight should be aggregated."""
    client = _make_mock_client()
    mock_scrape.side_effect = [
        SAMPLE_PROFILE_1.model_copy(),
        SAMPLE_PROFILE_2.model_copy(),
    ]

    result = analyze_pie(client, 12345, enrich_with_yahoo=False)

    apple = next(h for h in result.holdings if h["name"] == "Apple")
    # 0.04 * 0.60 + 0.01 * 0.40 = 0.024 + 0.004 = 0.028
    assert abs(apple["weight"] - 0.028) < 0.001
    assert len(apple["sources"]) == 2


@patch("t212_cli.tax.pie_analysis.scrape_justetf")
def test_analyze_pie_aggregates_countries(mock_scrape: MagicMock) -> None:
    client = _make_mock_client()
    mock_scrape.side_effect = [
        SAMPLE_PROFILE_1.model_copy(),
        SAMPLE_PROFILE_2.model_copy(),
    ]

    result = analyze_pie(client, 12345, enrich_with_yahoo=False)

    # US: 0.68*0.60 + 0.60*0.40 = 0.408 + 0.24 = 0.648
    assert abs(result.countries["United States"] - 0.648) < 0.001
    assert "Canada" in result.countries


@patch("t212_cli.tax.pie_analysis.scrape_justetf")
def test_analyze_pie_aggregates_sectors(mock_scrape: MagicMock) -> None:
    client = _make_mock_client()
    mock_scrape.side_effect = [
        SAMPLE_PROFILE_1.model_copy(),
        SAMPLE_PROFILE_2.model_copy(),
    ]

    result = analyze_pie(client, 12345, enrich_with_yahoo=False)

    # Technology: 0.30*0.60 = 0.18
    assert abs(result.sectors["Technology"] - 0.18) < 0.001
    # Energy: 0.99*0.40 = 0.396
    assert abs(result.sectors["Energy"] - 0.396) < 0.001


@patch("t212_cli.tax.pie_analysis.scrape_justetf")
def test_analyze_pie_to_dict(mock_scrape: MagicMock) -> None:
    client = _make_mock_client()
    mock_scrape.side_effect = [
        SAMPLE_PROFILE_1.model_copy(),
        SAMPLE_PROFILE_2.model_copy(),
    ]

    result = analyze_pie(client, 12345, enrich_with_yahoo=False)
    data = result.to_dict()

    assert data["pie_id"] == 12345
    assert data["total_components"] == 2
    assert "top_holdings" in data
    assert "countries" in data
    assert "sectors" in data
    assert data["top_holdings"][0]["name"] == "Exxon Mobil"  # highest weighted


@patch("t212_cli.tax.pie_analysis.scrape_justetf")
def test_analyze_pie_handles_no_data(mock_scrape: MagicMock) -> None:
    """Components where justETF returns None should be tracked as missing."""
    client = _make_mock_client()
    mock_scrape.return_value = None

    result = analyze_pie(client, 12345, enrich_with_yahoo=False)

    assert len(result.components_without_data) == 2
    assert result.total_accounted_weight == 0.0
