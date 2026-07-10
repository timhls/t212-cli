from datetime import datetime, date
from typing import List, Dict, Optional
from pydantic import BaseModel
from t212_cli.tax.models import AssetClass
from t212_cli.tax.config import get_instrument_config
from t212_cli.tax.market_data import get_historical_price


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
    gross_amount_eur: float = 0.0  # For dividends and interest
    foreign_tax_eur: float = 0.0  # For dividends


class FifoEngine:
    def __init__(self, target_year: Optional[int] = None):
        # ISIN -> List of Tranches
        self.inventory: Dict[str, List[Tranche]] = {}
        self.target_year = target_year

        # Loss buckets
        self.aktien_verlusttopf: float = 0.0
        self.sonstige_verlusttopf: float = 0.0

        # §23 EStG specific bucket (e.g. Physical ETC <= 1 year)
        self.private_veraeusserungs_gewinne: float = 0.0

        # Taxable gains tracked across whole history,
        # but we also want to track just for the target year
        self.taxable_gains: float = 0.0

        # Accumulators specifically for the target year
        self.year_taxable_gains: float = 0.0
        self.year_aktien_verlust_generated: float = 0.0
        self.year_sonstige_verlust_generated: float = 0.0
        self.year_private_veraeusserungs_gewinne_generated: float = 0.0

        # Foreign tax bucket
        self.anrechenbare_quellensteuer: float = 0.0
        self.year_anrechenbare_quellensteuer: float = 0.0

    def process_event(self, event: TaxEvent) -> None:
        if event.type == "BUY":
            self._handle_buy(event)
        elif event.type == "SELL":
            self._handle_sell(event)
        elif event.type == "DIVIDEND":
            self._handle_dividend(event)
        elif event.type == "INTEREST":
            self._handle_interest(event)

    def _handle_buy(self, event: TaxEvent) -> None:
        if event.isin not in self.inventory:
            self.inventory[event.isin] = []

        # Cost basis per share including fees
        total_cost = (event.quantity * event.price_eur) + event.fees_eur
        cost_per_share = total_cost / event.quantity if event.quantity > 0 else 0

        self.inventory[event.isin].append(
            Tranche(date=event.date, quantity=event.quantity, price_eur=cost_per_share)
        )

    def _handle_dividend(self, event: TaxEvent) -> None:
        config = get_instrument_config(event.isin)
        tfs_quote = config.tfs_quote if config else 0.0

        # Foreign tax calculation
        max_creditable_foreign_tax = event.gross_amount_eur * 0.15
        creditable_tax = min(event.foreign_tax_eur, max_creditable_foreign_tax)

        self.anrechenbare_quellensteuer += creditable_tax
        if self.target_year and event.date.year == self.target_year:
            self.year_anrechenbare_quellensteuer += creditable_tax

        taxable_dividend = event.gross_amount_eur * (1.0 - tfs_quote)

        # Offset against sonstige_verlusttopf
        if taxable_dividend > 0:
            offset = min(taxable_dividend, self.sonstige_verlusttopf)
            self.sonstige_verlusttopf -= offset
            taxable_dividend -= offset

        self.taxable_gains += taxable_dividend
        if self.target_year and event.date.year == self.target_year:
            self.year_taxable_gains += taxable_dividend

    def _handle_interest(self, event: TaxEvent) -> None:
        # Interest is fully taxable, no TFS, treated as regular capital gain
        taxable_interest = event.gross_amount_eur

        if taxable_interest > 0:
            offset = min(taxable_interest, self.sonstige_verlusttopf)
            self.sonstige_verlusttopf -= offset
            taxable_interest -= offset

        self.taxable_gains += taxable_interest
        if self.target_year and event.date.year == self.target_year:
            self.year_taxable_gains += taxable_interest

    def _handle_sell(self, event: TaxEvent) -> None:
        if event.isin not in self.inventory or not self.inventory[event.isin]:
            return

        remaining_to_sell = event.quantity

        # Accumulate gain for different buckets
        aktien_taxable_amount = 0.0
        sonstige_taxable_amount = 0.0
        private_veraeusserungs_gewinn = 0.0

        # Net sell price after fees
        net_proceeds = (event.quantity * event.price_eur) - event.fees_eur
        net_price_per_share = net_proceeds / event.quantity if event.quantity > 0 else 0

        tranches = self.inventory[event.isin]

        config = get_instrument_config(event.isin)
        tfs_quote = config.tfs_quote if config else 0.0
        asset_class = config.asset_class if config else AssetClass.UNKNOWN

        while remaining_to_sell > 0 and tranches:
            oldest = tranches[0]

            if oldest.quantity <= remaining_to_sell:
                # Consume whole tranche
                sold_qty = oldest.quantity
                tranche_vorabpauschale = oldest.accumulated_vorabpauschale
                tranches.pop(0)
            else:
                # Consume partial tranche
                sold_qty = remaining_to_sell
                # Proportional vorabpauschale
                ratio = sold_qty / oldest.quantity
                tranche_vorabpauschale = oldest.accumulated_vorabpauschale * ratio
                oldest.accumulated_vorabpauschale -= tranche_vorabpauschale
                oldest.quantity -= sold_qty

            remaining_to_sell -= sold_qty

            # Calculate gain for this tranche
            buy_value = sold_qty * oldest.price_eur
            sell_value = sold_qty * net_price_per_share

            # The gain before vorabpauschale deduction
            gross_gain = sell_value - buy_value

            # Subtract vorabpauschale
            net_gain_before_tfs = gross_gain - tranche_vorabpauschale

            # §23 EStG check for Physical ETCs
            if asset_class == AssetClass.PHYSICAL_ETC:
                days_held = (event.date - oldest.date).days
                if days_held > 365:
                    # > 1 year -> Tax free
                    pass
                else:
                    # <= 1 year -> private_veraeusserungs_gewinne
                    private_veraeusserungs_gewinn += net_gain_before_tfs
            else:
                # Normal stocks/ETFs
                taxable_amount = net_gain_before_tfs * (1.0 - tfs_quote)

                if asset_class == AssetClass.AKTIEN:
                    aktien_taxable_amount += taxable_amount
                else:
                    sonstige_taxable_amount += taxable_amount

        # Update buckets

        # 1. Aktien
        if aktien_taxable_amount < 0:
            self.aktien_verlusttopf += abs(aktien_taxable_amount)
            if self.target_year and event.date.year == self.target_year:
                self.year_aktien_verlust_generated += abs(aktien_taxable_amount)
        elif aktien_taxable_amount > 0:
            # §20 Abs.6 Satz 4 EStG: Aktiengewinne only offset Aktienverlusttopf.
            # Cross-bucket offsetting with sonstige Verlusttopf is legally
            # prohibited (BFH considers this unconstitutional under 2 BvL 3/21,
            # assessments are provisional since 2022 — we follow the statute).
            offset = min(aktien_taxable_amount, self.aktien_verlusttopf)
            self.aktien_verlusttopf -= offset
            aktien_taxable_amount -= offset
            self.taxable_gains += aktien_taxable_amount
            if self.target_year and event.date.year == self.target_year:
                self.year_taxable_gains += aktien_taxable_amount

        # 2. Sonstige
        if sonstige_taxable_amount < 0:
            self.sonstige_verlusttopf += abs(sonstige_taxable_amount)
            if self.target_year and event.date.year == self.target_year:
                self.year_sonstige_verlust_generated += abs(sonstige_taxable_amount)
        elif sonstige_taxable_amount > 0:
            offset = min(sonstige_taxable_amount, self.sonstige_verlusttopf)
            self.sonstige_verlusttopf -= offset
            sonstige_taxable_amount -= offset
            self.taxable_gains += sonstige_taxable_amount
            if self.target_year and event.date.year == self.target_year:
                self.year_taxable_gains += sonstige_taxable_amount

        # 3. Private Veräußerungsgeschäfte
        if private_veraeusserungs_gewinn != 0:
            self.private_veraeusserungs_gewinne += private_veraeusserungs_gewinn
            if self.target_year and event.date.year == self.target_year:
                self.year_private_veraeusserungs_gewinne_generated += (
                    private_veraeusserungs_gewinn
                )

    def process_year_end(
        self,
        year: int,
        basiszins: float,
        dividends_paid_by_isin: Optional[Dict[str, float]] = None,
    ) -> None:
        """Calculate Vorabpauschale at year end for all held tranches of ETFs/Fonds."""
        if dividends_paid_by_isin is None:
            dividends_paid_by_isin = {}

        for isin, tranches in self.inventory.items():
            config = get_instrument_config(isin)
            if not config:
                continue

            asset_class = config.asset_class

            # Only apply Vorabpauschale to ETFs/Fonds
            if asset_class not in [
                AssetClass.AKTIENFONDS,
                AssetClass.MISCHFONDS,
                AssetClass.IMMOBILIENFONDS,
                AssetClass.SONSTIGER_FONDS,
            ]:
                continue

            tfs_quote = config.tfs_quote
            ticker = config.yfinance_ticker or isin

            # Ensure price for start and end of year
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)

            # In a real app, these should be cached or pre-fetched to avoid yfinance spam
            try:
                start_price_year = get_historical_price(ticker, start_date)
                end_price_year = get_historical_price(ticker, end_date)
            except Exception:  # nosec
                continue

            if start_price_year is None or end_price_year is None:
                continue

            dividends_paid = dividends_paid_by_isin.get(isin, 0.0)
            # Full-year Wertsteigerung includes dividends (§18 Abs.1 InvStG)
            # Uses start-of-year market price, not tranche-specific price
            full_wertsteigerung = end_price_year - start_price_year + dividends_paid

            for tranche in tranches:
                # Determine start price
                if tranche.date.year == year:
                    start_price = tranche.price_eur
                    months_prior_to_purchase = tranche.date.month - 1
                elif tranche.date.year < year:
                    start_price = start_price_year
                    months_prior_to_purchase = 0
                else:
                    # Bought after this year, skip
                    continue

                # §18 Abs.1 Satz 2 InvStG: Basisertrag with 70% cost absorption
                # §18 Abs.2 InvStG: 1/12 reduction for mid-year purchases
                # applied to Basisertrag BEFORE min() comparison
                basisertrag = (
                    start_price
                    * basiszins
                    * 0.7
                    * (12 - months_prior_to_purchase)
                    / 12.0
                )

                # §18 Abs.1 InvStG: Vorabpauschale = max(0, min(Basisertrag, Wertsteigerung) - Dividends)
                # Wertsteigerung is NOT prorated for mid-year purchases
                vorabpauschale = max(
                    0.0, min(basisertrag, full_wertsteigerung) - dividends_paid
                )

                if vorabpauschale <= 0:
                    continue

                # Store FULL (pre-TFS) amount per §19 Abs.1 Satz 4 InvStG:
                # accumulated Vorabpauschale is deducted from sale gain
                # "ohne Berücksichtigung der Teilfreistellungen"
                tranche.accumulated_vorabpauschale += vorabpauschale * tranche.quantity

                # §18 Abs.3 InvStG: Vorabpauschale is taxable on first business
                # day of the following year. Apply TFS to the taxable portion.
                taxable_vorab = vorabpauschale * (1.0 - tfs_quote) * tranche.quantity
                self.taxable_gains += taxable_vorab
                if self.target_year and year == self.target_year:
                    self.year_taxable_gains += taxable_vorab

    def calculate_final_tax(
        self,
        kirchensteuer_rate: float = 0.0,
        sparer_pauschbetrag_available: float = 1000.0,
        personal_tax_rate: float = 0.0,
    ) -> float:
        """Calculate total tax liability.

        For §20 EStG gains: Abgeltungsteuer with Sparer-Pauschbetrag.
        For §23 EStG gains (physical ETC, crypto < 1yr): personal tax rate
        with €1,000 Freigrenze (all-or-nothing threshold).
        """
        # §20 EStG: Abgeltungsteuer path
        taxable = self.taxable_gains

        # Subtract Sparer-Pauschbetrag (§20 Abs.9 EStG)
        taxable -= sparer_pauschbetrag_available
        if taxable < 0:
            taxable = 0.0

        # §32d Abs.1 Satz 3 EStG: reduced rate when church tax applies
        effective_rate = 0.25 / (1 + 0.25 * kirchensteuer_rate)

        kapitalertragsteuer = taxable * effective_rate

        # Solidaritätszuschlag: 5.5% of Kapitalertragsteuer
        soli = kapitalertragsteuer * 0.055

        # Kirchensteuer: kist_rate of Kapitalertragsteuer
        kirchensteuer = kapitalertragsteuer * kirchensteuer_rate

        final_tax = kapitalertragsteuer + soli + kirchensteuer
        final_tax -= self.anrechenbare_quellensteuer

        # §23 EStG: Private Veräußerungsgeschäfte (physical gold, crypto < 1yr)
        # §23 Abs.3 Satz 5 EStG: Freigrenze €1,000 — all-or-nothing
        # If total §23 gains exceed €1,000: entire gain taxable at personal rate
        # If under €1,000: €0 tax. Losses offset only within §23.
        if self.private_veraeusserungs_gewinne > 1000.0 and personal_tax_rate > 0:
            s23_taxable = self.private_veraeusserungs_gewinne
            s23_tax = s23_taxable * personal_tax_rate
            s23_soli = s23_tax * 0.055
            s23_kirchensteuer = s23_tax * kirchensteuer_rate
            final_tax += s23_tax + s23_soli + s23_kirchensteuer

        return max(final_tax, 0.0)
