from datetime import datetime, timezone
from unittest.mock import patch

from t212_cli.tax.calculator import FifoEngine, TaxEvent
from t212_cli.tax.models import AssetClass, TaxInstrument


def test_vorabpauschale() -> None:
    engine = FifoEngine()

    # Mock instrument config
    with (
        patch("t212_cli.tax.calculator.get_instrument_config") as mock_config,
        patch("t212_cli.tax.calculator.get_historical_price") as mock_price,
    ):
        mock_config.return_value = TaxInstrument(
            asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.3
        )
        mock_price.side_effect = [100.0, 110.0]  # start price, end price

        # Buy in April 2024
        buy_event = TaxEvent(
            date=datetime(2024, 4, 15, tzinfo=timezone.utc),
            type="BUY",
            isin="IE00B4L5Y983",
            quantity=10.0,
            price_eur=100.0,
        )
        engine.process_event(buy_event)

        # Process year end for 2024
        # §18 InvStG: Basisertrag = 100 * 0.0255 * 0.7 = 1.785/share
        # §18 Abs.2: 1/12 rule — bought April, months_prior=3 → factor 9/12
        # Basisertrag (prorated) = 1.785 * 9/12 = 1.33875/share
        # Wertsteigerung = 110 - 100 = 10/share (full year, not prorated)
        # Vorabpauschale = min(1.33875, 10) = 1.33875/share
        # Total (pre-TFS, full amount per §19 Abs.1 Satz 4): 1.33875 * 10 = 13.3875
        engine.process_year_end(year=2024, basiszins=0.0255)

        tranche = engine.inventory["IE00B4L5Y983"][0]
        # accumulated_vorabpauschale stores FULL amount (without TFS)
        assert abs(tranche.accumulated_vorabpauschale - 13.3875) < 0.001
        # §18 Abs.3 InvStG: taxable portion = 13.3875 * (1 - 0.30) = 9.37125
        assert abs(engine.taxable_gains - 9.37125) < 0.001

        # Sell in 2025
        sell_event = TaxEvent(
            date=datetime(2025, 1, 10, tzinfo=timezone.utc),
            type="SELL",
            isin="IE00B4L5Y983",
            quantity=10.0,
            price_eur=120.0,
        )

        engine.process_event(sell_event)

        # Gross gain = 10 * 120 - 10 * 100 = 200
        # §19 Abs.1 Satz 4: minus FULL accumulated Vorabpauschale = 200 - 13.3875 = 186.6125
        # Apply TFS = 186.6125 * 0.7 = 130.62875
        # Total taxable_gains = 9.37125 (vorab) + 130.62875 (sale) = 140.00
        assert abs(engine.taxable_gains - 140.00) < 0.001


def test_dividends() -> None:
    engine = FifoEngine()

    with patch("t212_cli.tax.calculator.get_instrument_config") as mock_config:
        mock_config.return_value = TaxInstrument(
            asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.3
        )

        div_event = TaxEvent(
            date=datetime(2024, 5, 1, tzinfo=timezone.utc),
            type="DIVIDEND",
            isin="US123",
            gross_amount_eur=100.0,
            foreign_tax_eur=20.0,  # 20%
        )

        engine.process_event(div_event)

        # Taxable amount = 100 * 0.7 = 70
        assert engine.taxable_gains == 70.0

        # Foreign tax limit is 15%
        assert engine.anrechenbare_quellensteuer == 15.0


def test_interest() -> None:
    engine = FifoEngine()

    int_event = TaxEvent(
        date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        type="INTEREST",
        isin="CASH",
        gross_amount_eur=50.0,
    )

    engine.process_event(int_event)

    assert engine.taxable_gains == 50.0
    # Does not have TFS, full amount goes to taxable_gains


def test_physical_etc() -> None:
    engine = FifoEngine()

    with patch("t212_cli.tax.calculator.get_instrument_config") as mock_config:
        mock_config.return_value = TaxInstrument(
            asset_class=AssetClass.PHYSICAL_ETC, tfs_quote=0.0
        )

        buy_event = TaxEvent(
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            type="BUY",
            isin="ETC123",
            quantity=10.0,
            price_eur=100.0,
        )

        # Sell <= 1 year
        sell_event_short = TaxEvent(
            date=datetime(2024, 12, 1, tzinfo=timezone.utc),
            type="SELL",
            isin="ETC123",
            quantity=5.0,
            price_eur=110.0,
        )

        engine.process_event(buy_event)
        engine.process_event(sell_event_short)

        assert engine.private_veraeusserungs_gewinne == 50.0
        assert engine.taxable_gains == 0.0  # Standard taxable gains untouched

        # Sell > 1 year
        sell_event_long = TaxEvent(
            date=datetime(2025, 1, 5, tzinfo=timezone.utc),  # > 365 days
            type="SELL",
            isin="ETC123",
            quantity=5.0,
            price_eur=150.0,
        )

        engine.process_event(sell_event_long)

        assert (
            engine.private_veraeusserungs_gewinne == 50.0
        )  # Untouched since previous sell
        assert engine.taxable_gains == 0.0  # Tax free!


def test_final_tax() -> None:
    engine = FifoEngine()

    engine.taxable_gains = 11000.0
    engine.anrechenbare_quellensteuer = 100.0

    # 0% Kirchensteuer
    # Taxable = 11000 - 1000 = 10000
    # KapESt = 10000 * 0.25 = 2500
    # Soli = 2500 * 0.055 = 137.5
    # Total = 2637.5 - 100 = 2537.5
    tax_0 = engine.calculate_final_tax(0.0, 1000.0)
    assert abs(tax_0 - 2537.5) < 0.001

    # 8% Kirchensteuer
    # Rate = 0.25 / 1.02 = 0.245098...
    # KapESt = 2450.98039
    # Soli = 134.8039
    # KiSt = 196.078
    # Total = 2781.862 - 100 = 2681.862
    tax_8 = engine.calculate_final_tax(0.08, 1000.0)
    assert abs(tax_8 - 2681.8627) < 0.001

    # 9% Kirchensteuer
    # Rate = 0.25 / 1.0225 = 0.24449877...
    # KapESt = 2444.98777
    # Soli = 134.474327
    # KiSt = 220.048899
    # Total = 2799.5109 - 100 = 2699.5109
    tax_9 = engine.calculate_final_tax(0.09, 1000.0)
    assert abs(tax_9 - 2699.51099) < 0.001
