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


class EtfHolding(BaseModel):
    name: str
    isin: str | None = None
    weight: float  # 0.0544 for 5.44%


class EtfProfile(BaseModel):
    isin: str
    name: str | None = None
    ter: float | None = None  # 0.0012 for 0.12%
    fund_size_eur: float | None = None  # in millions
    distribution_policy: str | None = None  # "Accumulating" / "Distributing"
    replication: str | None = None
    fund_currency: str | None = None
    holdings: list[EtfHolding] = Field(default_factory=list)
    countries: dict[str, float] = Field(default_factory=dict)  # name -> weight
    sectors: dict[str, float] = Field(default_factory=dict)  # name -> weight
    asset_classes: dict[str, float] = Field(default_factory=dict)


class TaxConfig(BaseModel):
    instruments: dict[str, TaxInstrument] = Field(
        default_factory=dict
    )  # ISIN -> TaxInstrument mapping
