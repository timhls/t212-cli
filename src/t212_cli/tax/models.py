from enum import StrEnum
from pydantic import BaseModel, Field


class AssetClass(StrEnum):
    AKTIEN = "Aktien"
    AKTIENFONDS = "Aktienfonds"
    MISCHFONDS = "Mischfonds"
    IMMOBILIENFONDS = "Immobilienfonds"
    SONSTIGER_FONDS = "Sonstiger Fonds"
    PHYSICAL_ETC = "Physical ETC"
    SYNTHETIC_ETC = "Synthetic ETC"
    BOND = "Bond"
    UNKNOWN = "Unknown"


class TaxInstrument(BaseModel):
    name: str | None = None
    asset_class: AssetClass = AssetClass.UNKNOWN
    tfs_quote: float = 0.0  # Teilfreistellungsquote (e.g. 0.30 for 30%)
    yfinance_ticker: str | None = (
        None  # Explicit mapping to Yahoo Finance ticker for Vorabpauschale
    )


class TaxConfig(BaseModel):
    instruments: dict[str, TaxInstrument] = Field(
        default_factory=dict
    )  # ISIN -> TaxInstrument mapping
