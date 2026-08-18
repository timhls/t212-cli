"""Markdown and CSV renderers for Trading 212 card transactions.

The markdown format mirrors a hand-validated 2025 tax document: a summary
table (purchases, ATM withdrawals, verifications, declined/reverted), monthly
tables with a Notes column (cashback, FX, ATM fees, round-ups), and monthly
subtotals that sum to the net spend.

Amount semantics (validated against the T212 web app display):

- Completed purchases/ATM withdrawals: ``-charged_amount()`` (for ATM
  withdrawals with a fee this is ``amount`` which includes the fee — the app
  displays it that way too).
- Refunds: ``+billingAmount``.
- Declined / reverted / card verifications: ``0.00`` (nothing was charged),
  with the attempted amount in Notes.
"""

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from t212_cli.models.cards import CardStatus, CardTransaction, CardTransactionType

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _sort_key(tx: CardTransaction) -> datetime:
    return tx.timeCreated or _EPOCH


_TYPE_LABELS = {
    CardTransactionType.PURCHASE: "Purchase",
    CardTransactionType.ATM_WITHDRAWAL: "ATM withdrawal",
    CardTransactionType.CARD_VERIFICATION: "Card verification",
    CardTransactionType.REFUND: "Refund",
}

_REASON_LABELS = {
    "INCORRECT_EXPIRY_DATE": "incorrect expiry date",
    "EXPIRATION_REVERSAL": "authorisation reversal",
    "UNVERIFIED_WITHDRAWAL_LIMIT_EXCEEDED": "withdrawal limit exceeded",
}


@dataclass
class _CardSpan:
    count: int = 0
    first: datetime = _EPOCH
    last: datetime = _EPOCH

    def add(self, when: datetime) -> None:
        self.count += 1
        self.first = when if self.first == _EPOCH else min(self.first, when)
        self.last = max(self.last, when)


@dataclass(frozen=True)
class CardSummary:
    purchases_count: int
    purchases_total: float
    atm_count: int
    atm_total: float
    refunds_count: int
    refunds_total: float
    verifications: int
    reverted: int
    declined: int

    @property
    def net_total(self) -> float:
        return self.purchases_total + self.atm_total - self.refunds_total

    @property
    def charged_count(self) -> int:
        return self.purchases_count + self.atm_count


def _fmt_out(amount: float) -> str:
    """Format a money-out total: ``-340.00`` for spend, ``0.00`` for zero."""
    return f"{-amount:.2f}" if amount else "0.00"


def summarize(transactions: list[CardTransaction]) -> CardSummary:
    """Aggregate counts and totals by type/status."""
    purchases = [
        t
        for t in transactions
        if t.status == CardStatus.COMPLETED and t.type == CardTransactionType.PURCHASE
    ]
    atms = [
        t
        for t in transactions
        if t.status == CardStatus.COMPLETED
        and t.type == CardTransactionType.ATM_WITHDRAWAL
    ]
    refunds = [
        t
        for t in transactions
        if t.status == CardStatus.COMPLETED and t.type == CardTransactionType.REFUND
    ]
    return CardSummary(
        purchases_count=len(purchases),
        purchases_total=sum(t.charged_amount() for t in purchases),
        atm_count=len(atms),
        atm_total=sum(t.charged_amount() for t in atms),
        refunds_count=len(refunds),
        refunds_total=sum(t.billingAmount or 0.0 for t in refunds),
        verifications=sum(
            1 for t in transactions if t.type == CardTransactionType.CARD_VERIFICATION
        ),
        reverted=sum(1 for t in transactions if t.status == CardStatus.REVERTED),
        declined=sum(1 for t in transactions if t.status == CardStatus.DECLINED),
    )


def _type_label(tx: CardTransaction) -> str:
    if tx.type is None:
        return ""
    return _TYPE_LABELS.get(tx.type, tx.type.value)


def _billing_currency(transactions: list[CardTransaction]) -> str:
    """Most frequent transaction currency as a proxy for the account currency."""
    counts: dict[str, int] = {}
    for tx in transactions:
        if tx.currencyCode:
            counts[tx.currencyCode] = counts.get(tx.currencyCode, 0) + 1
    if not counts:
        return "EUR"
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _category(tx: CardTransaction) -> str:
    """First segment of the (double-space separated) enhanced category."""
    merchant = tx.merchant
    if not merchant:
        return ""
    raw = merchant.enhancedCategory or merchant.category or ""
    return raw.split("  ")[0]


def _esc(value: str) -> str:
    return value.replace("|", "/")


def _status(tx: CardTransaction) -> str:
    reason = _REASON_LABELS.get(tx.statusReason or "", tx.statusReason or "")
    if tx.status == CardStatus.DECLINED:
        return "Declined" + (f" ({reason})" if reason else "")
    if tx.status == CardStatus.REVERTED:
        return "Reverted" + (f" ({reason})" if reason else "")
    if tx.status == CardStatus.PENDING:
        return "Pending"
    return "Completed"


def _signed_amount(tx: CardTransaction) -> float:
    """Net effect on the card balance (negative = money out)."""
    if tx.type == CardTransactionType.REFUND and tx.status == CardStatus.COMPLETED:
        return tx.billingAmount or 0.0
    if tx.status in (CardStatus.DECLINED, CardStatus.REVERTED, CardStatus.PENDING):
        return 0.0
    if tx.type == CardTransactionType.CARD_VERIFICATION:
        return 0.0
    return -tx.charged_amount()


def _notes(tx: CardTransaction, billing_currency: str) -> str:
    notes: list[str] = []
    conversion = tx.currencyConversion
    if conversion and (
        conversion.originalAmount is not None or conversion.originalCurrency
    ):
        original = (
            conversion.originalAmount
            if conversion.originalAmount is not None
            else tx.amount
        )
        currency = conversion.originalCurrency or tx.currencyCode or ""
        notes.append(f"original: {original} {currency}".rstrip())
    elif tx.currencyCode and tx.currencyCode != billing_currency:
        notes.append(f"original: {tx.amount} {tx.currencyCode}")
    if tx.atmWithdrawalFee:
        notes.append(
            f"includes ATM fee {tx.currencyCode or billing_currency} {tx.atmWithdrawalFee:.2f}"
        )
    if tx.t212Cashback and tx.t212Cashback.amount:
        notes.append(
            f"cashback {tx.t212Cashback.currencyCode or billing_currency} {tx.t212Cashback.amount:.2f}"
        )
    if (
        tx.roundUp
        and tx.roundUp.investedMoney
        and tx.roundUp.investedMoney.amount is not None
    ):
        money = tx.roundUp.investedMoney
        notes.append(
            f"spare change {money.currencyCode or billing_currency} {money.amount:.2f}"
        )
    if tx.status == CardStatus.REVERTED:
        notes.append(f"charge of {tx.billingAmount or 0.0:.2f} reversed")
    if tx.status == CardStatus.DECLINED:
        notes.append(f"not charged ({tx.billingAmount or 0.0:.2f} attempted)")
    return "; ".join(notes)


def render_csv(transactions: list[CardTransaction], tz: ZoneInfo) -> str:
    """Render transactions as CSV (ascending by time), one row per transaction."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "transaction_id",
            "internal_id",
            "date",
            "time",
            "timezone",
            "created_utc",
            "merchant",
            "category",
            "enhanced_category",
            "country",
            "card_last_four",
            "type",
            "status",
            "status_reason",
            "payment_channel",
            "amount",
            "currency",
            "billing_amount",
            "atm_fee",
            "net_effect",
            "cashback",
            "round_up",
            "notes",
        ]
    )
    billing_currency = _billing_currency(transactions)
    for tx in sorted(transactions, key=_sort_key):
        local = tx.timeCreated.astimezone(tz) if tx.timeCreated else None
        merchant = tx.merchant
        writer.writerow(
            [
                tx.clientReferenceId or "",
                tx.id,
                local.strftime("%Y-%m-%d") if local else "",
                local.strftime("%H:%M") if local else "",
                tz.key,
                tx.timeCreated.isoformat() if tx.timeCreated else "",
                merchant.name if merchant else "",
                _category(tx),
                (
                    merchant.enhancedCategory
                    if merchant and merchant.enhancedCategory
                    else ""
                ),
                merchant.countryCode if merchant else "",
                tx.cardLastFour or "",
                _type_label(tx),
                _status(tx),
                tx.statusReason or "",
                tx.paymentChannel or "",
                f"{tx.amount:.2f}" if tx.amount is not None else "",
                tx.currencyCode or "",
                f"{tx.billingAmount:.2f}" if tx.billingAmount is not None else "",
                f"{tx.atmWithdrawalFee:.2f}" if tx.atmWithdrawalFee is not None else "",
                f"{_signed_amount(tx):.2f}",
                f"{tx.t212Cashback.amount:.2f}"
                if tx.t212Cashback and tx.t212Cashback.amount
                else "",
                (
                    f"{tx.roundUp.investedMoney.amount:.2f}"
                    if tx.roundUp
                    and tx.roundUp.investedMoney
                    and tx.roundUp.investedMoney.amount is not None
                    else ""
                ),
                _notes(tx, billing_currency),
            ]
        )
    return out.getvalue()


def render_markdown(
    transactions: list[CardTransaction],
    tz: ZoneInfo,
    *,
    from_date: str,
    to_date: str,
) -> str:
    """Render the tax-document style markdown report."""
    ordered = sorted(transactions, key=_sort_key)
    summary = summarize(ordered)
    currency = _billing_currency(ordered)

    cards: dict[str, _CardSpan] = {}
    for tx in ordered:
        if tx.timeCreated:
            cards.setdefault(tx.cardLastFour or "????", _CardSpan()).add(tx.timeCreated)

    first_time = (
        ordered[0].timeCreated.astimezone(tz)
        if ordered and ordered[0].timeCreated
        else None
    )
    last_time = (
        ordered[-1].timeCreated.astimezone(tz)
        if ordered and ordered[-1].timeCreated
        else None
    )

    lines: list[str] = []
    lines.append("# Trading 212 — Card Transactions")
    lines.append("")
    lines.append(
        "- **Source:** Trading 212 card transaction history (`rest/cards/v1/transaction-executions`)"
    )
    card_parts = []
    for last_four in sorted(cards):
        span = cards[last_four]
        card_parts.append(
            f"••••{last_four} ({span.count} transaction{'' if span.count == 1 else 's'}, "
            f"{span.first.astimezone(tz):%Y-%m-%d} – {span.last.astimezone(tz):%Y-%m-%d})"
        )
    if card_parts:
        lines.append(f"- **Cards:** {', '.join(card_parts)}")
    if first_time and last_time:
        lines.append(
            f"- **Period:** {from_date} – {to_date} (transactions span "
            f"{first_time:%Y-%m-%d} – {last_time:%Y-%m-%d})"
        )
    lines.append(f"- **Billing currency:** {currency} (times in {tz.key})")
    lines.append(f"- **Extracted:** {datetime.now(tz):%Y-%m-%d}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| | Count | Total ({currency}) |")
    lines.append("|---|------:|------------:|")
    lines.append(
        f"| Purchases (completed) | {summary.purchases_count} | {_fmt_out(summary.purchases_total)} |"
    )
    lines.append(
        f"| ATM withdrawals (completed) | {summary.atm_count} | {_fmt_out(summary.atm_total)} |"
    )
    if summary.refunds_count:
        lines.append(
            f"| Refunds | {summary.refunds_count} | +{summary.refunds_total:.2f} |"
        )
    lines.append(
        f"| Card verifications ({currency} 0.00 hold) | {summary.verifications} | 0.00 |"
    )
    lines.append(f"| Reversed charges | {summary.reverted} | 0.00 |")
    lines.append(f"| Declined (not charged) | {summary.declined} | 0.00 |")
    lines.append(
        f"| **Net spend** | **{summary.charged_count} transactions** | **{_fmt_out(summary.net_total)}** |"
    )
    lines.append("")

    months: dict[tuple[int, int], list[CardTransaction]] = {}
    for tx in ordered:
        if not tx.timeCreated:
            continue
        local = tx.timeCreated.astimezone(tz)
        months.setdefault((local.year, local.month), []).append(tx)

    month_names = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }
    for year, month in sorted(months):
        items = months[(year, month)]
        month_summary = summarize(items)
        lines.append(
            f"## {month_names[month]} {year} "
            f"({len(items)} transactions, {_fmt_out(month_summary.net_total)} {currency})"
        )
        lines.append("")
        lines.append(
            f"| Date | Time | Merchant | Category | Type | Status | Amount ({currency}) | Notes |"
        )
        lines.append(
            "|------|------|----------|----------|------|--------|-------------:|-------|"
        )
        for tx in items:
            if not tx.timeCreated:
                continue
            local = tx.timeCreated.astimezone(tz)
            merchant = tx.merchant.name if tx.merchant and tx.merchant.name else ""
            amount = _signed_amount(tx)
            amount_str = f"{amount:.2f}" if amount == 0 else f"{amount:+.2f}"
            when = f"{local:%Y-%m-%d} | {local:%H:%M}" if local else " | "
            lines.append(
                f"| {when} | {_esc(merchant)} | {_esc(_category(tx))} "
                f"| {_type_label(tx)} | {_status(tx)} "
                f"| {amount_str} | {_esc(_notes(tx, currency)) or ' '} |"
            )
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- Amounts are the amounts as charged; declined transactions were not charged "
        "and reversed charges net to zero."
    )
    lines.append(
        '- "Spare change" entries are round-up auto-investments, not additional card charges.'
    )
    return "\n".join(lines) + "\n"
