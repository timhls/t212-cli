import re
from typing import Any, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests

from t212_cli.tax.models import EtfHolding, EtfProfile
from t212_cli.tax.yahoo_finance import get_etf_funds_data


def enrich_profile_with_yahoo(profile: EtfProfile, ticker: str) -> EtfProfile:
    """Enrich an ETF profile with supplementary Yahoo Finance data.

    Fills in gaps that justETF didn't provide: asset classes, holdings,
    and sector weightings.
    """
    yf_data = get_etf_funds_data(ticker)
    if yf_data:
        if yf_data.get("asset_classes"):
            profile.asset_classes = yf_data["asset_classes"]
        if not profile.holdings and yf_data.get("holdings"):
            profile.holdings = [
                EtfHolding(
                    name=h.get("name", h.get("symbol", "")),
                    weight=h.get("weight", 0.0),
                )
                for h in yf_data["holdings"]
            ]
        if not profile.sectors and yf_data.get("sector_weightings"):
            profile.sectors = yf_data["sector_weightings"]
    return profile


def scrape_justetf(isin: str) -> Optional[EtfProfile]:
    url = f"https://www.justetf.com/en/etf-profile.html?isin={isin}"
    try:
        response = requests.get(url, timeout=15, impersonate="chrome110")
        if response.status_code != 200:
            return None
    except requests.RequestsError:
        return None

    soup = BeautifulSoup(response.text, "lxml")
    profile = EtfProfile(isin=isin)

    name = _extract_name(soup)
    if name:
        profile.name = name

    basics = _extract_basics(soup)
    if basics:
        profile.ter = basics.get("ter")
        profile.fund_size_eur = basics.get("fund_size_eur")
        profile.distribution_policy = basics.get("distribution_policy")
        profile.replication = basics.get("replication")
        profile.fund_currency = basics.get("fund_currency")

    holdings = _extract_holdings(soup)
    if holdings:
        profile.holdings = holdings

    countries = _extract_table_section(soup, "Countries")
    if countries:
        profile.countries = countries

    sectors = _extract_table_section(soup, "Sectors")
    if sectors:
        profile.sectors = sectors

    return profile


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        text = text.split("|")[0].strip()
        return text if text else None
    return None


def _extract_basics(soup: BeautifulSoup) -> dict[str, Any]:
    """Extract ETF basics from the justETF page.

    justETF renders the basics as a table where each row carries
    ``data-testid="etf-basics_row_{slug}"`` and most value cells carry
    ``data-testid="tl_etf-basics_value_{slug}"``. The fund-size cell is an
    exception (no testid on its value), so it is located via its row's second
    ``<td>``. Older versions of the page used ``<dt>/<dd>`` siblings.
    """
    basics: dict[str, Any] = {}

    # Map justETF's slugified keys to our field names.
    slug_to_field = {
        "ter": "ter",
        "fund-currency": "fund_currency",
        "replication": "replication",
        "distribution-policy": "distribution_policy",
    }

    for slug, field in slug_to_field.items():
        cell = soup.find(attrs={"data-testid": f"tl_etf-basics_value_{slug}"})
        if not cell:
            continue
        raw = cell.get_text(strip=True)
        if not raw or raw == "-":
            continue

        if field == "ter":
            m = re.search(r"([\d.]+)\s*%", raw)
            if m:
                basics[field] = float(m.group(1)) / 100.0
        elif field == "replication":
            # Cell contains two spans: replication + method. Joined text works.
            basics[field] = raw
        else:
            basics[field] = raw

    # Fund size: locate the row by label, take the second <td>'s text.
    # Structure: <tr data-testid="etf-basics_row_fund-size">
    #              <td class="vallabel">Fund size</td>
    #              <td>EUR 19,830 m <span .../></td>
    fs_row = soup.find(attrs={"data-testid": "etf-basics_row_fund-size"})
    if fs_row:
        tds = fs_row.find_all("td", recursive=False) or fs_row.find_all("td")
        if len(tds) >= 2:
            raw_size = tds[1].get_text(strip=True)
            m = re.search(r"EUR\s*([\d,.]+)\s*m", raw_size, re.IGNORECASE)
            if m:
                basics["fund_size_eur"] = float(m.group(1).replace(",", ""))

    return basics


def _extract_holdings(soup: BeautifulSoup) -> list[EtfHolding]:
    holdings: list[EtfHolding] = []

    for link in soup.find_all("a", href=lambda x: x and "/stock-profiles/" in x):
        if link.find_parent("nav"):
            continue

        name = link.get_text(strip=True)
        if not name:
            continue

        href = link.get("href")
        if not isinstance(href, str):
            continue
        isin_match = re.search(r"/stock-profiles/([A-Z0-9]+)", href)
        holding_isin = isin_match.group(1) if isin_match else None

        row = link.find_parent("tr") or link.find_parent("div")
        if not row:
            continue
        row_text = row.get_text(" ", strip=True)
        pct_match = re.search(r"([\d.]+)%", row_text)
        if not pct_match:
            continue

        weight = float(pct_match.group(1)) / 100.0
        holdings.append(EtfHolding(name=name, isin=holding_isin, weight=weight))

    return holdings


def _extract_table_section(soup: BeautifulSoup, heading_text: str) -> dict[str, float]:
    result: dict[str, float] = {}

    for h3 in soup.find_all("h3"):
        if heading_text not in h3.get_text():
            continue
        parent = h3.find_parent("div")
        if not parent:
            continue
        table = parent.find("table")
        if not table:
            continue
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            name = tds[-2].get_text(strip=True)
            weight_text = tds[-1].get_text(strip=True)
            m = re.search(r"([\d.]+)%", weight_text)
            if name and m:
                result[name] = float(m.group(1)) / 100.0
        break

    return result
