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

    # Aktien gain offsets both buckets
    assert engine.aktien_verlusttopf == 0.0
    assert engine.sonstige_verlusttopf == 0.0
    assert engine.taxable_gains == 100.0


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
