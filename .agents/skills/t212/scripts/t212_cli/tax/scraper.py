import re
from curl_cffi import requests
from bs4 import BeautifulSoup
from typing import Optional
from t212_cli.tax.models import TaxInstrument, AssetClass


def scrape_finanzfluss(isin: str) -> Optional[TaxInstrument]:
    """Scrape ETF/ETC tax classification from Finanzfluss."""
    # Attempt ETF route first
    url = f"https://www.finanzfluss.de/informer/etf/{isin}/"
    try:
        response = requests.get(url, timeout=10, impersonate="chrome110")

        # If not found as ETF, try ETC route
        if response.status_code == 404:
            url = f"https://www.finanzfluss.de/informer/etc/{isin}/"
            response = requests.get(url, timeout=10, impersonate="chrome110")

        if response.status_code != 200:
            return None

        html = response.text
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()

        instrument = TaxInstrument()

        # Check Teilfreistellung (TFS)
        tfs_match = re.search(r"(\d+)%\s*Teilfreistellung", text)
        if tfs_match:
            instrument.tfs_quote = float(tfs_match.group(1)) / 100.0

            # Map TFS back to Asset Class for ETFs
            if instrument.tfs_quote >= 0.30:
                instrument.asset_class = AssetClass.AKTIENFONDS
            elif instrument.tfs_quote >= 0.15:
                instrument.asset_class = AssetClass.MISCHFONDS
            else:
                instrument.asset_class = AssetClass.SONSTIGER_FONDS

        # Check if Physical ETC
        if "physisch" in text.lower() and "etc" in text.lower():
            instrument.asset_class = AssetClass.PHYSICAL_ETC
            instrument.tfs_quote = 0.0

        return instrument

    except requests.RequestsError:
        return None
