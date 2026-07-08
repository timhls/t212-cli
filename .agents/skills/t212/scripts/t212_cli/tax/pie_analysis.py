"""Pie analysis service: deep-dive into pie holdings, regions, and sectors."""

from collections import defaultdict
from typing import Any, Optional

from t212_cli.client.base import Trading212Client
from t212_cli.models import AccountBucketInstrumentsDetailedResponse
from t212_cli.tax.justetf import scrape_justetf, enrich_profile_with_yahoo
from t212_cli.tax.models import EtfProfile


class PieAnalysisResult:
    """Aggregated analysis of a pie's underlying holdings."""

    def __init__(self, pie_id: int) -> None:
        self.pie_id = pie_id
        self.holdings: list[dict[str, Any]] = []
        self.countries: dict[str, float] = defaultdict(float)
        self.sectors: dict[str, float] = defaultdict(float)
        self.etf_profiles: list[dict[str, Any]] = []
        self.total_accounted_weight: float = 0.0
        self.total_components: int = 0
        self.components_without_data: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        ranked = sorted(self.holdings, key=lambda x: x["weight"], reverse=True)
        return {
            "pie_id": self.pie_id,
            "total_components": self.total_components,
            "total_accounted_weight_pct": round(self.total_accounted_weight * 100, 2),
            "unaccounted_weight_pct": round(
                (1.0 - self.total_accounted_weight) * 100, 2
            ),
            "components_without_data": self.components_without_data,
            "etf_profiles": self.etf_profiles,
            "top_holdings": ranked,
            "countries": dict(
                sorted(self.countries.items(), key=lambda x: x[1], reverse=True)
            ),
            "sectors": dict(
                sorted(self.sectors.items(), key=lambda x: x[1], reverse=True)
            ),
        }


def enrich_pie_components(
    client: Trading212Client, pie_id: int
) -> tuple[AccountBucketInstrumentsDetailedResponse, list[dict[str, Any]]]:
    """Fetch pie detail and resolve each component ticker to its ISIN.

    Returns the raw pie detail and a list of component info dicts with
    ticker, isin, current_share, expected_share.
    """
    detail = client.get_pie_by_id(pie_id)
    components = detail.instruments or []

    comp_info: list[dict[str, Any]] = []
    for c in components:
        isin = client.resolve_isin_from_ticker(c.ticker or "")
        comp_info.append(
            {
                "ticker": c.ticker,
                "isin": isin,
                "current_share": c.currentShare or 0.0,
                "expected_share": c.expectedShare or 0.0,
                "name": None,
            }
        )

    return detail, comp_info


def analyze_pie(
    client: Trading212Client,
    pie_id: int,
    enrich_with_yahoo: bool = True,
) -> PieAnalysisResult:
    """Deep-dive analysis of a pie: fetch all underlying ETF holdings,
    aggregate by company, geography, and sector. Weights each holding
    by the component's current share in the pie.

    Args:
        client: Authenticated Trading212Client
        pie_id: The pie ID to analyze
        enrich_with_yahoo: If True, fall back to Yahoo Finance for ETFs
            that justETF doesn't cover

    Returns:
        PieAnalysisResult with aggregated holdings, countries, sectors
    """
    result = PieAnalysisResult(pie_id)

    _, comp_info = enrich_pie_components(client, pie_id)
    result.total_components = len(comp_info)

    holding_agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"weight": 0.0, "sources": set(), "isin": None}
    )

    for ci in comp_info:
        isin = ci["isin"]
        weight = ci["current_share"]
        ticker = ci["ticker"]

        if not isin:
            result.components_without_data.append(ticker or "unknown")
            continue

        profile: Optional[EtfProfile] = scrape_justetf(isin)

        if profile and enrich_with_yahoo and ticker:
            profile = enrich_profile_with_yahoo(profile, ticker)

        if not profile or (
            not profile.holdings and not profile.countries and not profile.sectors
        ):
            result.components_without_data.append(ticker or isin)
            continue

        ci["name"] = profile.name if profile else None
        result.etf_profiles.append(ci)

        if profile.holdings:
            for h in profile.holdings:
                key = h.name
                holding_agg[key]["weight"] += h.weight * weight
                holding_agg[key]["sources"].add(ticker or "")
                if h.isin:
                    holding_agg[key]["isin"] = h.isin

        if profile.countries:
            for country, cw in profile.countries.items():
                result.countries[country] += cw * weight

        if profile.sectors:
            for sector, sw in profile.sectors.items():
                result.sectors[sector] += sw * weight

    for name, info in holding_agg.items():
        result.holdings.append(
            {
                "name": name,
                "isin": info["isin"],
                "weight": info["weight"],
                "weight_pct": round(info["weight"] * 100, 4),
                "sources": sorted(info["sources"]),
            }
        )

    result.total_accounted_weight = sum(
        ci["current_share"] for ci in result.etf_profiles
    )

    return result
