import csv
import io
from typing import Any
from zoneinfo import ZoneInfo

from t212_cli.card_report import render_csv, render_markdown, summarize
from t212_cli.models.cards import CardTransaction

TZ = ZoneInfo("Europe/Berlin")


def _tx(tx_id: int, created: str, **overrides: Any) -> CardTransaction:
    base: dict[str, Any] = {
        "id": tx_id,
        "clientReferenceId": f"REF{tx_id}",
        "amount": 10.0,
        "billingAmount": 10.0,
        "currencyCode": "EUR",
        "status": "COMPLETED",
        "type": "PURCHASE",
        "timeCreated": created,
        "merchant": {
            "name": "Rewe",
            "category": "RETAIL_STORES",
            "enhancedCategory": "GROCERY STORES  SUPERMARKETS",
            "countryCode": "DEU",
        },
        "cardLastFour": "7164",
        "paymentChannel": "POS",
    }
    base.update(overrides)
    return CardTransaction(**base)


def _fixtures() -> list[CardTransaction]:
    return [
        # October: plain purchase with cashback and round-up
        _tx(
            1,
            "2025-10-07T16:02:24Z",
            t212Cashback={"amount": 0.16, "currencyCode": "EUR"},
            roundUp={"investedMoney": {"amount": 0.30, "currencyCode": "EUR"}},
        ),
        # ATM withdrawal with fee: amount includes fee, billing excludes it
        _tx(
            2,
            "2025-12-23T14:16:04Z",
            amount=100.10,
            billingAmount=100.00,
            atmWithdrawalFee=0.10,
            type="ATM_WITHDRAWAL",
            merchant={
                "name": "Landesbank Baden-Württemberg",
                "category": "CUSTOMER FINANCIAL INSTIT",
            },
        ),
        # Declined ATM — not charged
        _tx(
            3,
            "2025-12-24T09:00:00Z",
            billingAmount=150.00,
            status="DECLINED",
            statusReason="UNVERIFIED_WITHDRAWAL_LIMIT_EXCEEDED",
            type="ATM_WITHDRAWAL",
        ),
        # Reverted purchase — nets to zero
        _tx(
            4,
            "2025-12-25T09:00:00Z",
            billingAmount=1.00,
            status="REVERTED",
            statusReason="EXPIRATION_REVERSAL",
        ),
        # Foreign-currency card verification — zero effect
        _tx(
            5,
            "2025-12-26T09:00:00Z",
            amount=0.0,
            billingAmount=0.0,
            currencyCode="CNY",
            status="COMPLETED",
            type="CARD_VERIFICATION",
            merchant={"name": "Weixin", "category": "MISCELLANEOUS"},
        ),
        # Refund — positive effect
        _tx(
            6,
            "2025-12-27T09:00:00Z",
            billingAmount=12.50,
            type="REFUND",
            merchant={"name": "Lufthansa", "category": "AIR FRANCE"},
        ),
        # Large purchase (merchant name contains a pipe)
        _tx(
            7,
            "2025-12-31T10:34:45Z",
            billingAmount=330.00,
            merchant={"name": "Pankratz | GmbH", "category": "EATING PLACES"},
        ),
    ]


class TestSummarize:
    def test_counts_and_totals(self) -> None:
        s = summarize(_fixtures())
        assert s.purchases_count == 2  # ids 1, 7 (reverted 4 and refund 6 excluded)
        assert s.purchases_total == 10.0 + 330.0
        assert s.atm_count == 1
        assert s.atm_total == 100.10  # fee-inclusive amount
        assert s.refunds_count == 1
        assert s.refunds_total == 12.50
        assert s.verifications == 1
        assert s.reverted == 1
        assert s.declined == 1
        assert s.net_total == 340.00 + 100.10 - 12.50


class TestMarkdown:
    def test_structure_and_amounts(self) -> None:
        md = render_markdown(
            _fixtures(), TZ, from_date="2025-10-01", to_date="2025-12-31"
        )
        assert md.startswith("# Trading 212 — Card Transactions")
        assert "| Purchases (completed) | 2 | -340.00 |" in md
        assert "| ATM withdrawals (completed) | 1 | -100.10 |" in md
        assert "| Refunds | 1 | +12.50 |" in md
        assert "**Net spend** | **3 transactions** | **-427.60** |" in md
        # Months: October and December
        assert "## October 2025 (1 transactions, -10.00 EUR)" in md
        assert "## December 2025 (6 transactions, -417.60 EUR)" in md
        # Berlin time conversion: 16:02Z -> 18:02 CEST
        assert "| 2025-10-07 | 18:02 | Rewe | GROCERY STORES" in md
        # ATM fee-inclusive amount and note
        assert "| -100.10 |" in md
        assert "includes ATM fee EUR 0.10" in md
        # Declined: zero amount, attempted amount noted
        assert "| 0.00 |" in md
        assert "not charged (150.00 attempted)" in md
        assert "Declined (withdrawal limit exceeded)" in md
        # Reverted
        assert "Reverted (authorisation reversal)" in md
        assert "charge of 1.00 reversed" in md
        # Foreign currency verification
        assert "Card verification" in md
        assert "original: 0.0 CNY" in md
        # Refund with plus sign
        assert "| +12.50 |" in md
        # Pipes in merchant names are escaped
        assert "Pankratz / GmbH" in md
        assert "Pankratz | GmbH" not in md
        # Cashback + spare change notes
        assert "cashback EUR 0.16" in md
        assert "spare change EUR 0.30" in md

    def test_empty_period_renders_header(self) -> None:
        md = render_markdown([], TZ, from_date="2025-01-01", to_date="2025-12-31")
        assert "# Trading 212 — Card Transactions" in md
        assert "| Purchases (completed) | 0 | 0.00 |" in md


class TestCsv:
    def test_rows_and_net_effect(self) -> None:
        rows = list(csv.reader(io.StringIO(render_csv(_fixtures(), TZ))))
        header, body = rows[0], rows[1:]
        assert "transaction_id" in header
        assert "net_effect" in header
        assert len(body) == 7
        by_id = {int(r[header.index("internal_id")]): r for r in body}
        assert by_id[1][header.index("net_effect")] == "-10.00"
        assert by_id[2][header.index("net_effect")] == "-100.10"
        assert by_id[2][header.index("atm_fee")] == "0.10"
        assert by_id[3][header.index("net_effect")] == "0.00"
        assert by_id[4][header.index("net_effect")] == "0.00"
        assert by_id[5][header.index("net_effect")] == "0.00"
        assert by_id[6][header.index("net_effect")] == "12.50"
        assert by_id[7][header.index("net_effect")] == "-330.00"
        # Local time conversion
        assert by_id[1][header.index("date")] == "2025-10-07"
        assert by_id[1][header.index("time")] == "18:02"
        assert by_id[1][header.index("timezone")] == "Europe/Berlin"

    def test_empty_csv_has_only_header(self) -> None:
        rows = list(csv.reader(io.StringIO(render_csv([], TZ))))
        assert len(rows) == 1
