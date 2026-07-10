from datetime import datetime
from t212_cli.tax.calculator import FifoEngine, TaxEvent
from t212_cli.tax.models import AssetClass, TaxInstrument
from unittest.mock import patch, MagicMock


def test_fifo_engine_buy() -> None:
    engine = FifoEngine()
    event = TaxEvent(
        date=datetime(2024, 1, 1),
        type="BUY",
        isin="US0378331005",
        quantity=10.0,
        price_eur=150.0,
        fees_eur=5.0,
    )
    engine.process_event(event)

    assert "US0378331005" in engine.inventory
    tranches = engine.inventory["US0378331005"]
    assert len(tranches) == 1

    # Total cost = (10 * 150) + 5 = 1505
    # Cost per share = 150.5
    assert tranches[0].quantity == 10.0
    assert tranches[0].price_eur == 150.5


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_fifo_engine_sell_full_gain(mock_get_config: MagicMock) -> None:
    # Mock to be an Aktienfonds with 30% Teilfreistellung
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.3
    )

    engine = FifoEngine(target_year=2024)
    buy_event = TaxEvent(
        date=datetime(2023, 1, 1),
        type="BUY",
        isin="IE00B4L5Y983",
        quantity=10.0,
        price_eur=100.0,
        fees_eur=0.0,
    )
    engine.process_event(buy_event)

    sell_event = TaxEvent(
        date=datetime(2024, 1, 1),
        type="SELL",
        isin="IE00B4L5Y983",
        quantity=10.0,
        price_eur=200.0,  # 1000 EUR gain
        fees_eur=0.0,
    )
    engine.process_event(sell_event)

    assert len(engine.inventory["IE00B4L5Y983"]) == 0

    # 1000 EUR gain * (1 - 0.3) = 700 EUR taxable
    assert engine.taxable_gains == 700.0
    assert engine.year_taxable_gains == 700.0
    assert engine.sonstige_verlusttopf == 0.0


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_fifo_engine_sell_partial_loss_aktien(mock_get_config: MagicMock) -> None:
    # Mock to be plain Aktien
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIEN, tfs_quote=0.0
    )

    engine = FifoEngine(target_year=2024)
    # Buy 20 shares @ 100 = 2000
    engine.process_event(
        TaxEvent(
            date=datetime(2023, 1, 1),
            type="BUY",
            isin="US0378331005",
            quantity=20.0,
            price_eur=100.0,
        )
    )

    # Sell 10 shares @ 50 = 500
    # Gain = 500 - 1000 = -500 (Loss)
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 1),
            type="SELL",
            isin="US0378331005",
            quantity=10.0,
            price_eur=50.0,
        )
    )

    assert engine.inventory["US0378331005"][0].quantity == 10.0
    assert engine.aktien_verlusttopf == 500.0
    assert engine.year_aktien_verlust_generated == 500.0

    # Sell remaining 10 shares @ 200 = 2000
    # Gain = 2000 - 1000 = +1000
    # Should offset against 500 loss -> net taxable 500
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 2, 1),
            type="SELL",
            isin="US0378331005",
            quantity=10.0,
            price_eur=200.0,
        )
    )

    assert engine.aktien_verlusttopf == 0.0
    assert engine.taxable_gains == 500.0
    assert engine.year_taxable_gains == 500.0


def test_fifo_engine_sell_not_owned() -> None:
    engine = FifoEngine()
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 1),
            type="SELL",
            isin="MISSING",
            quantity=10.0,
            price_eur=100.0,
        )
    )
    # Should safely return without crash
    assert "MISSING" not in engine.inventory


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_fifo_engine_loss_offsetting_complex(mock_get_config: MagicMock) -> None:
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIEN, tfs_quote=0.0
    )
    engine = FifoEngine(target_year=2024)

    engine.aktien_verlusttopf = 100.0
    engine.sonstige_verlusttopf = 200.0

    # Buy 1 @ 10
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 1),
            type="BUY",
            isin="ABC",
            quantity=1.0,
            price_eur=10.0,
        )
    )
    # Sell 1 @ 410 -> Gain = 400
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 2),
            type="SELL",
            isin="ABC",
            quantity=1.0,
            price_eur=410.0,
        )
    )

    # §20 Abs.6 Satz 4 EStG: Aktiengewinne only offset Aktienverlusttopf
    assert engine.aktien_verlusttopf == 0.0
    assert engine.sonstige_verlusttopf == 200.0  # NOT touched by Aktiengewinn
    assert engine.taxable_gains == 300.0  # 400 gain - 100 aktien offset


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_fifo_engine_etf_loss(mock_get_config: MagicMock) -> None:
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.3
    )
    engine = FifoEngine(target_year=2024)

    # Buy 1 @ 100
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 1),
            type="BUY",
            isin="ETF",
            quantity=1.0,
            price_eur=100.0,
        )
    )
    # Sell 1 @ 0 -> Loss = 100. With 30% TFS, loss is 70
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 2),
            type="SELL",
            isin="ETF",
            quantity=1.0,
            price_eur=0.0,
        )
    )

    assert engine.sonstige_verlusttopf == 70.0
    assert engine.year_sonstige_verlust_generated == 70.0


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_fifo_engine_multi_tranche_sell(mock_get_config: MagicMock) -> None:
    """FIFO matching correctly consumes the oldest tranche first across multiple buy tranches."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIEN, tfs_quote=0.0
    )
    engine = FifoEngine(target_year=2024)

    # First buy: 5 shares @ 100 EUR
    engine.process_event(
        TaxEvent(
            date=datetime(2023, 1, 1),
            type="BUY",
            isin="US1234",
            quantity=5.0,
            price_eur=100.0,
        )
    )
    # Second buy: 5 shares @ 200 EUR
    engine.process_event(
        TaxEvent(
            date=datetime(2023, 6, 1),
            type="BUY",
            isin="US1234",
            quantity=5.0,
            price_eur=200.0,
        )
    )

    assert len(engine.inventory["US1234"]) == 2

    # Sell 7 shares @ 300 EUR each
    # FIFO: consumes all 5 from tranche 1 and 2 from tranche 2
    # Gain from tranche 1: 5 * (300 - 100) = 1000
    # Gain from tranche 2: 2 * (300 - 200) = 200
    # Total gain = 1200 EUR
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 1),
            type="SELL",
            isin="US1234",
            quantity=7.0,
            price_eur=300.0,
        )
    )

    # 3 shares remain from tranche 2
    assert len(engine.inventory["US1234"]) == 1
    assert engine.inventory["US1234"][0].quantity == 3.0
    assert engine.inventory["US1234"][0].price_eur == 200.0

    assert engine.taxable_gains == 1200.0
    assert engine.year_taxable_gains == 1200.0


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_fifo_engine_sonstige_gain_does_not_use_aktien_bucket(
    mock_get_config: MagicMock,
) -> None:
    """Sonstige (non-Aktien) gains must not consume the aktien_verlusttopf."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.0
    )
    engine = FifoEngine(target_year=2024)
    engine.aktien_verlusttopf = 500.0
    engine.sonstige_verlusttopf = 0.0

    # Buy 1 share @ 100 EUR (ETF / Aktienfonds)
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 1),
            type="BUY",
            isin="ETF1",
            quantity=1.0,
            price_eur=100.0,
        )
    )
    # Sell 1 share @ 300 EUR -> gain = 200 EUR
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 6, 1),
            type="SELL",
            isin="ETF1",
            quantity=1.0,
            price_eur=300.0,
        )
    )

    # aktien_verlusttopf must remain untouched for non-Aktien gains
    assert engine.aktien_verlusttopf == 500.0
    assert engine.taxable_gains == 200.0
    assert engine.year_taxable_gains == 200.0


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_fifo_engine_year_taxable_gains_isolation(mock_get_config: MagicMock) -> None:
    """year_taxable_gains only accumulates gains from the target year, not prior years."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIEN, tfs_quote=0.0
    )
    engine = FifoEngine(target_year=2024)

    # Buy shares in 2022
    engine.process_event(
        TaxEvent(
            date=datetime(2022, 1, 1),
            type="BUY",
            isin="US9999",
            quantity=10.0,
            price_eur=50.0,
        )
    )
    # Sell half in 2023 (outside target year) -> gain = 5 * (100 - 50) = 250
    engine.process_event(
        TaxEvent(
            date=datetime(2023, 6, 1),
            type="SELL",
            isin="US9999",
            quantity=5.0,
            price_eur=100.0,
        )
    )
    # Sell remainder in 2024 (target year) -> gain = 5 * (150 - 50) = 500
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 3, 1),
            type="SELL",
            isin="US9999",
            quantity=5.0,
            price_eur=150.0,
        )
    )

    assert engine.taxable_gains == 750.0  # 250 + 500 cumulative
    assert engine.year_taxable_gains == 500.0  # only target-year gain


# ---------------------------------------------------------------------------
# Validation tests against the reference:
# references/german-capital-investment-taxation.md
# ("Die Besteuerung privater Kapitalanlagen", legal stand July 2027)
# ---------------------------------------------------------------------------


# === Abgeltungsteuer rate validation (document table lines 22-27) ===


def test_abgeltungsteuer_rate_no_church() -> None:
    """Effective rate without church tax: 26.375% (25% + 5.5% Soli on that)."""
    engine = FifoEngine()
    engine.taxable_gains = 10000.0
    tax = engine.calculate_final_tax(
        kirchensteuer_rate=0.0, sparer_pauschbetrag_available=0.0
    )
    # 25% + 1.375% Soli = 26.375%
    assert abs(tax - 2637.50) < 0.01


def test_abgeltungsteuer_rate_8pct_church() -> None:
    """Effective rate with 8% church tax (BY, BW): 27.82%."""
    engine = FifoEngine()
    engine.taxable_gains = 10000.0
    tax = engine.calculate_final_tax(
        kirchensteuer_rate=0.08, sparer_pauschbetrag_available=0.0
    )
    # KeSt 24.51% + Soli 1.348% + KiSt 1.96% = 27.8186%
    assert abs(tax - 2781.86) < 0.5


def test_abgeltungsteuer_rate_9pct_church() -> None:
    """Effective rate with 9% church tax (RLP): 27.99%."""
    engine = FifoEngine()
    engine.taxable_gains = 10000.0
    tax = engine.calculate_final_tax(
        kirchensteuer_rate=0.09, sparer_pauschbetrag_available=0.0
    )
    # KeSt 24.45% + Soli 1.345% + KiSt 2.20% = 27.9951%
    assert abs(tax - 2799.51) < 0.5


# === Document example: €3,000 interest, 9% church tax RLP (lines 59-80) ===


def test_document_interest_example() -> None:
    """€3000 interest - €1000 Sparer-Pauschbetrag = €2000 taxable.
    9% church tax RLP: total tax should be €559.90 (document: €559.88)."""
    engine = FifoEngine()
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 6, 1),
            type="INTEREST",
            isin="INTEREST",
            gross_amount_eur=3000.0,
        )
    )
    tax = engine.calculate_final_tax(
        kirchensteuer_rate=0.09, sparer_pauschbetrag_available=1000.0
    )
    assert abs(tax - 559.90) < 0.5


# === Sparer-Pauschbetrag edge cases ===


def test_sparer_pauschbetrag_exact_offset() -> None:
    """Gains exactly equal to Sparer-Pauschbetrag → zero tax."""
    engine = FifoEngine()
    engine.taxable_gains = 1000.0
    tax = engine.calculate_final_tax(sparer_pauschbetrag_available=1000.0)
    assert tax == 0.0


def test_sparer_pauschbetrag_partial() -> None:
    """Gains above Sparer-Pauschbetrag → only excess taxed."""
    engine = FifoEngine()
    engine.taxable_gains = 1500.0
    tax = engine.calculate_final_tax(sparer_pauschbetrag_available=1000.0)
    # 500 * 26.375% = 131.875
    assert abs(tax - 131.88) < 0.01


# === §20 Abs.6 Satz 4 EStG: Aktien losses only offset Aktien gains ===


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_aktien_loss_does_not_offset_sonstige_gain(
    mock_get_config: MagicMock,
) -> None:
    """Aktien losses cannot reduce sonstige gains (§20 Abs.6 Satz 4 EStG)."""
    # First: Aktien loss
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIEN, tfs_quote=0.0
    )
    engine = FifoEngine(target_year=2024)
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 1),
            type="BUY",
            isin="STOCK",
            quantity=10.0,
            price_eur=100.0,
        )
    )
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 2),
            type="SELL",
            isin="STOCK",
            quantity=10.0,
            price_eur=50.0,  # -500 loss
        )
    )
    assert engine.aktien_verlusttopf == 500.0

    # Now: ETF (sonstige) gain
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.30
    )
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 6, 1),
            type="BUY",
            isin="ETF",
            quantity=10.0,
            price_eur=100.0,
        )
    )
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 6, 2),
            type="SELL",
            isin="ETF",
            quantity=10.0,
            price_eur=200.0,  # +1000 gain, -30% TFS = 700 taxable
        )
    )
    # Aktien loss bucket untouched, full 700 sonstige taxable
    assert engine.aktien_verlusttopf == 500.0
    assert engine.taxable_gains == 700.0


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_aktien_gain_only_offsets_aktien_loss(
    mock_get_config: MagicMock,
) -> None:
    """Aktien gains offset Aktien losses, NOT sonstige losses."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIEN, tfs_quote=0.0
    )
    engine = FifoEngine(target_year=2024)
    engine.sonstige_verlusttopf = 300.0
    engine.aktien_verlusttopf = 100.0

    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 1),
            type="BUY",
            isin="X",
            quantity=1.0,
            price_eur=10.0,
        )
    )
    engine.process_event(
        TaxEvent(
            date=datetime(2024, 1, 2),
            type="SELL",
            isin="X",
            quantity=1.0,
            price_eur=510.0,  # 500 gain
        )
    )
    # 500 gain - 100 aktien loss = 400 taxable
    # sonstige bucket untouched
    assert engine.aktien_verlusttopf == 0.0
    assert engine.sonstige_verlusttopf == 300.0
    assert engine.taxable_gains == 400.0


# === §23 Abs.3 Satz 5 EStG: Freigrenze €1,000 (all-or-nothing) ===


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_s23_freigrenze_under_1000_no_tax(mock_get_config: MagicMock) -> None:
    """§23 gains under €1,000 → no tax regardless of personal rate."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.PHYSICAL_ETC, tfs_quote=0.0
    )
    engine = FifoEngine(target_year=2026)
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 1, 1),
            type="BUY",
            isin="GOLD",
            quantity=1.0,
            price_eur=8000.0,
        )
    )
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 8, 1),
            type="SELL",
            isin="GOLD",
            quantity=1.0,
            price_eur=8900.0,  # 900 gain, < 1000
        )
    )
    tax = engine.calculate_final_tax(personal_tax_rate=0.42)
    assert tax == 0.0


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_s23_freigrenze_over_1000_entire_gain_taxed(
    mock_get_config: MagicMock,
) -> None:
    """§23 gains over €1,000 → entire gain taxable at personal rate."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.PHYSICAL_ETC, tfs_quote=0.0
    )
    engine = FifoEngine(target_year=2026)
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 1, 1),
            type="BUY",
            isin="GOLD",
            quantity=1.0,
            price_eur=8000.0,
        )
    )
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 8, 1),
            type="SELL",
            isin="GOLD",
            quantity=1.0,
            price_eur=9500.0,  # 1500 gain, > 1000
        )
    )
    # Entire 1500 at 42% + 5.5% Soli = 1500 * 0.42 * 1.055 = 664.65
    tax = engine.calculate_final_tax(personal_tax_rate=0.42)
    assert abs(tax - 664.65) < 0.01


# === FIFO for crypto (§23 Abs.1 Satz 1 Nr.2 Satz 3 EStG) ===


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_crypto_fifo_matching(mock_get_config: MagicMock) -> None:
    """Crypto FIFO: oldest buys consumed first. Document example lines 258-281."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.UNKNOWN, tfs_quote=0.0
    )
    engine = FifoEngine(target_year=2026)
    # Treat crypto as §23 asset. For this test we verify FIFO ordering only.
    # Buy 0.10 @ 40000
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 2, 1),
            type="BUY",
            isin="BTC",
            quantity=0.10,
            price_eur=40000.0,
        )
    )
    # Buy 0.10 @ 50000
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 5, 1),
            type="BUY",
            isin="BTC",
            quantity=0.10,
            price_eur=50000.0,
        )
    )
    # Sell 0.15 @ 60000
    # FIFO: 0.10 from Feb (cost 4000) + 0.05 from May (cost 2500)
    # Proceeds: 0.15 * 60000 = 9000
    # Gain: 9000 - 4000 - 2500 = 2500
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 11, 1),
            type="SELL",
            isin="BTC",
            quantity=0.15,
            price_eur=60000.0,
        )
    )
    # Document says gain = €2500
    # As UNKNOWN asset with 0% TFS, it goes to sonstige bucket
    assert abs(engine.taxable_gains - 2500.0) < 0.01
    # Remaining: 0.05 BTC from May @ 50000
    assert len(engine.inventory["BTC"]) == 1
    assert abs(engine.inventory["BTC"][0].quantity - 0.05) < 0.0001


# === Vorabpauschale formula (document example lines 143-168) ===


@patch("t212_cli.tax.calculator.get_instrument_config")
@patch("t212_cli.tax.calculator.get_historical_price")
def test_vorabpauschale_document_example(
    mock_get_price: MagicMock,
    mock_get_config: MagicMock,
) -> None:
    """Document example: €20k Aktien-ETF, basiszins 3.2%, gain €1000, no dividends.
    Vorabpauschale = €448, taxable (30% TFS) = €313.60."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.30
    )
    # start_price = €200/share * 100 shares = €20,000
    # end_price = €210/share * 100 shares = €21,000
    mock_get_price.side_effect = [200.0, 210.0]

    engine = FifoEngine(target_year=2026)
    engine.process_event(
        TaxEvent(
            date=datetime(2025, 6, 1),
            type="BUY",
            isin="ETF",
            quantity=100.0,
            price_eur=200.0,
        )
    )
    engine.process_year_end(year=2026, basiszins=0.032)

    # Vorabpauschale per share = 200 * 0.032 * 0.7 = 4.48
    # Total = 4.48 * 100 shares = 448
    # Stored in accumulated_vorabpauschale (pre-TFS, full amount)
    assert abs(engine.inventory["ETF"][0].accumulated_vorabpauschale - 448.0) < 0.01
    # Taxable portion = 448 * (1 - 0.30) = 313.60
    assert abs(engine.taxable_gains - 313.60) < 0.01


@patch("t212_cli.tax.calculator.get_instrument_config")
@patch("t212_cli.tax.calculator.get_historical_price")
def test_vorabpauschale_midyear_purchase_1_12_rule(
    mock_get_price: MagicMock,
    mock_get_config: MagicMock,
) -> None:
    """§18 Abs.2 InvStG: 1/12 reduction applied to Basisertrag BEFORE min().
    Buy in July → 6 months prior → factor = 6/12 = 0.5."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.30
    )
    mock_get_price.side_effect = [200.0, 210.0]

    engine = FifoEngine(target_year=2026)
    # Buy on July 1 → month=7, months_prior = 6
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 7, 1),
            type="BUY",
            isin="ETF",
            quantity=100.0,
            price_eur=200.0,
        )
    )
    engine.process_year_end(year=2026, basiszins=0.032)

    # Basisertrag = 200 * 0.032 * 0.7 * (12-6)/12 = 200 * 0.032 * 0.7 * 0.5 = 2.24/share
    # Wertsteigerung = 210 - 200 + 0 = 10/share (full year, not prorated)
    # min(2.24, 10) - 0 = 2.24
    # Total pre-TFS: 2.24 * 100 = 224
    assert abs(engine.inventory["ETF"][0].accumulated_vorabpauschale - 224.0) < 0.01
    # Taxable: 224 * 0.7 = 156.80
    assert abs(engine.taxable_gains - 156.80) < 0.01


@patch("t212_cli.tax.calculator.get_instrument_config")
@patch("t212_cli.tax.calculator.get_historical_price")
def test_vorabpauschale_deducted_at_sale_without_tfs(
    mock_get_price: MagicMock,
    mock_get_config: MagicMock,
) -> None:
    """§19 Abs.1 Satz 4 InvStG: accumulated Vorabpauschale deducted from sale
    gain in FULL (without TFS reduction), even though TFS applies to the gain."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.30
    )
    mock_get_price.side_effect = [200.0, 210.0]

    engine = FifoEngine(target_year=2027)
    # Buy 100 @ 200
    engine.process_event(
        TaxEvent(
            date=datetime(2025, 6, 1),
            type="BUY",
            isin="ETF",
            quantity=100.0,
            price_eur=200.0,
        )
    )
    # Year end: Vorabpauschale = 4.48/share * 100 = 448
    engine.process_year_end(year=2026, basiszins=0.032)
    assert abs(engine.inventory["ETF"][0].accumulated_vorabpauschale - 448.0) < 0.01

    # Now sell in 2027 at €250
    # Gross gain = (250 - 200) * 100 = 5000
    # Minus Vorabpauschale (full, pre-TFS): 5000 - 448 = 4552
    # After TFS: 4552 * (1 - 0.30) = 3186.4
    engine.process_event(
        TaxEvent(
            date=datetime(2027, 3, 1),
            type="SELL",
            isin="ETF",
            quantity=100.0,
            price_eur=250.0,
        )
    )
    # taxable_gains includes: 313.60 (Vorabpauschale 2026) + 3186.40 (sale 2027)
    # year_taxable_gains only 2027 = 3186.40
    assert abs(engine.year_taxable_gains - 3186.40) < 0.5


@patch("t212_cli.tax.calculator.get_instrument_config")
@patch("t212_cli.tax.calculator.get_historical_price")
def test_vorabpauschale_zero_when_loss(
    mock_get_price: MagicMock,
    mock_get_config: MagicMock,
) -> None:
    """§18 Abs.1 InvStG: if Wertsteigerung is negative, Vorabpauschale = 0."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.30
    )
    # Price went DOWN: 200 → 180
    mock_get_price.side_effect = [200.0, 180.0]

    engine = FifoEngine(target_year=2026)
    engine.process_event(
        TaxEvent(
            date=datetime(2025, 6, 1),
            type="BUY",
            isin="ETF",
            quantity=100.0,
            price_eur=200.0,
        )
    )
    engine.process_year_end(year=2026, basiszins=0.032)
    # Wertsteigerung = 180 - 200 + 0 = -20 < 0 → Vorabpauschale = 0
    assert engine.inventory["ETF"][0].accumulated_vorabpauschale == 0.0
    assert engine.taxable_gains == 0.0


# === Dividend Teilfreistellung (§20 InvStG) ===


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_dividend_teilfreistellung_aktienfonds(
    mock_get_config: MagicMock,
) -> None:
    """Aktienfonds dividends: 30% Teilfreistellung → 70% taxable."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.30
    )
    engine = FifoEngine()
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 3, 1),
            type="DIVIDEND",
            isin="ETF",
            gross_amount_eur=1000.0,
        )
    )
    # 1000 * (1 - 0.30) = 700 taxable
    assert engine.taxable_gains == 700.0


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_dividend_teilfreistellung_mischfonds(
    mock_get_config: MagicMock,
) -> None:
    """Mischfonds dividends: 15% Teilfreistellung → 85% taxable."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.MISCHFONDS, tfs_quote=0.15
    )
    engine = FifoEngine()
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 3, 1),
            type="DIVIDEND",
            isin="MIX",
            gross_amount_eur=1000.0,
        )
    )
    assert engine.taxable_gains == 850.0


# === Quellensteuer (foreign withholding tax credit) ===


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_dividend_foreign_tax_credit(mock_get_config: MagicMock) -> None:
    """Foreign withholding tax creditable up to 15% of gross dividend."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.0
    )
    engine = FifoEngine()
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 3, 1),
            type="DIVIDEND",
            isin="US_ETF",
            gross_amount_eur=1000.0,
            foreign_tax_eur=150.0,  # exactly 15%
        )
    )
    assert engine.anrechenbare_quellensteuer == 150.0
    # Taxable = 1000 - 1000 Pauschbetrag = 0 → tax = 0 before Quellensteuer
    # With 0 Pauschbetrag: tax = 1000 * 0.26375 - 150 = 113.75
    tax = engine.calculate_final_tax(sparer_pauschbetrag_available=0.0)
    assert abs(tax - 113.75) < 0.01


@patch("t212_cli.tax.calculator.get_instrument_config")
def test_dividend_foreign_tax_capped_at_15pct(
    mock_get_config: MagicMock,
) -> None:
    """Foreign tax above 15% is NOT creditable (excess lost)."""
    mock_get_config.return_value = TaxInstrument(
        asset_class=AssetClass.AKTIENFONDS, tfs_quote=0.0
    )
    engine = FifoEngine()
    engine.process_event(
        TaxEvent(
            date=datetime(2026, 3, 1),
            type="DIVIDEND",
            isin="US_ETF",
            gross_amount_eur=1000.0,
            foreign_tax_eur=250.0,  # 25%, but only 15% creditable
        )
    )
    assert engine.anrechenbare_quellensteuer == 150.0  # capped at 15%
