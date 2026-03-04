from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel
from t212_cli.tax.models import AssetClass
from t212_cli.tax.config import get_instrument_config


class Tranche(BaseModel):
    date: datetime
    quantity: float
    price_eur: float  # Includes ancillary costs divided by quantity
    accumulated_vorabpauschale: float = 0.0


class TaxEvent(BaseModel):
    date: datetime
    type: str  # BUY, SELL, DIVIDEND, INTEREST
    isin: str
    quantity: float = 0.0
    price_eur: float = 0.0
    fees_eur: float = 0.0


class FifoEngine:
    def __init__(self, target_year: Optional[int] = None):
        # ISIN -> List of Tranches
        self.inventory: Dict[str, List[Tranche]] = {}
        self.target_year = target_year

        # Loss buckets
        self.aktien_verlusttopf: float = 0.0
        self.sonstige_verlusttopf: float = 0.0

        # Taxable gains tracked across whole history,
        # but we also want to track just for the target year
        self.taxable_gains: float = 0.0

        # Accumulators specifically for the target year
        self.year_taxable_gains: float = 0.0
        self.year_aktien_verlust_generated: float = 0.0
        self.year_sonstige_verlust_generated: float = 0.0

    def process_event(self, event: TaxEvent) -> None:
        if event.type == "BUY":
            self._handle_buy(event)
        elif event.type == "SELL":
            self._handle_sell(event)

    def _handle_buy(self, event: TaxEvent) -> None:
        if event.isin not in self.inventory:
            self.inventory[event.isin] = []

        # Cost basis per share including fees
        total_cost = (event.quantity * event.price_eur) + event.fees_eur
        cost_per_share = total_cost / event.quantity if event.quantity > 0 else 0

        self.inventory[event.isin].append(
            Tranche(date=event.date, quantity=event.quantity, price_eur=cost_per_share)
        )

    def _handle_sell(self, event: TaxEvent) -> None:
        if event.isin not in self.inventory or not self.inventory[event.isin]:
            # Selling something we don't have recorded - error case, skip or warn
            return

        remaining_to_sell = event.quantity
        total_gain_loss = 0.0

        # Net sell price after fees
        net_proceeds = (event.quantity * event.price_eur) - event.fees_eur
        net_price_per_share = net_proceeds / event.quantity if event.quantity > 0 else 0

        tranches = self.inventory[event.isin]

        while remaining_to_sell > 0 and tranches:
            oldest = tranches[0]

            if oldest.quantity <= remaining_to_sell:
                # Consume whole tranche
                sold_qty = oldest.quantity
                tranches.pop(0)
            else:
                # Consume partial tranche
                sold_qty = remaining_to_sell
                oldest.quantity -= remaining_to_sell

            remaining_to_sell -= sold_qty

            # Calculate gain for this tranche
            buy_value = sold_qty * oldest.price_eur
            sell_value = sold_qty * net_price_per_share
            gain = sell_value - buy_value

            total_gain_loss += gain

        # Apply Teilfreistellung
        config = get_instrument_config(event.isin)
        tfs_quote = config.tfs_quote if config else 0.0
        asset_class = config.asset_class if config else AssetClass.UNKNOWN

        # Determine if it's tax-free (like physical ETC > 1 year)
        # For a full implementation, we'd check dates here for §23 EStG

        taxable_amount = total_gain_loss * (1.0 - tfs_quote)

        # Route to loss buckets
        if asset_class == AssetClass.AKTIEN:
            if taxable_amount < 0:
                self.aktien_verlusttopf += abs(taxable_amount)
                if self.target_year and event.date.year == self.target_year:
                    self.year_aktien_verlust_generated += abs(taxable_amount)
            else:
                # Offset against aktien bucket first
                offset = min(taxable_amount, self.aktien_verlusttopf)
                self.aktien_verlusttopf -= offset
                taxable_amount -= offset

                # If still positive, offset against sonstige bucket
                if taxable_amount > 0:
                    offset2 = min(taxable_amount, self.sonstige_verlusttopf)
                    self.sonstige_verlusttopf -= offset2
                    taxable_amount -= offset2

                self.taxable_gains += taxable_amount
                if self.target_year and event.date.year == self.target_year:
                    self.year_taxable_gains += taxable_amount
        else:
            # ETFs, ETCs, etc.
            if taxable_amount < 0:
                self.sonstige_verlusttopf += abs(taxable_amount)
                if self.target_year and event.date.year == self.target_year:
                    self.year_sonstige_verlust_generated += abs(taxable_amount)
            else:
                offset = min(taxable_amount, self.sonstige_verlusttopf)
                self.sonstige_verlusttopf -= offset
                taxable_amount -= offset
                self.taxable_gains += taxable_amount
                if self.target_year and event.date.year == self.target_year:
                    self.year_taxable_gains += taxable_amount
