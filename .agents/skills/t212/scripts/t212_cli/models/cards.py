"""Pydantic models for the private Trading 212 cards web API.

These model responses from ``https://live.services.trading212.com/rest/cards/v1``,
the API backing the web app's card transaction list. It is *not* part of the
public ``/api/v0`` API and is only reachable with browser session cookies.

Field names are camelCase to match the wire format (consistent with the
generated public-API models). Unknown fields are ignored defensively since
this API is undocumented and may change without notice.
"""

from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict


class CardStatus(StrEnum):
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    DECLINED = "DECLINED"
    REVERTED = "REVERTED"


class CardTransactionType(StrEnum):
    PURCHASE = "PURCHASE"
    ATM_WITHDRAWAL = "ATM_WITHDRAWAL"
    CARD_VERIFICATION = "CARD_VERIFICATION"
    REFUND = "REFUND"


class _LooseModel(BaseModel):
    """Base that tolerates unknown/renamed fields from the undocumented API."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class CardMerchantLogo(_LooseModel):
    url: str | None = None


class CardMerchant(_LooseModel):
    name: str | None = None
    category: str | None = None
    enhancedCategory: str | None = None
    address: str | None = None
    countryCode: str | None = None
    logo: CardMerchantLogo | None = None


class CardCurrencyConversion(_LooseModel):
    """FX conversion details for non-billing-currency transactions.

    The exact field names of this object were never observed in real data
    (all sampled transactions were billing-currency or zero-amount
    verifications); fields are optional and extra ones are ignored.
    """

    originalAmount: float | None = None
    originalCurrency: str | None = None
    rate: float | None = None


class CardCashback(_LooseModel):
    amount: float | None = None
    currencyCode: str | None = None
    status: str | None = None


class CardRoundUpMoney(_LooseModel):
    amount: float | None = None
    currencyCode: str | None = None


class CardRoundUp(_LooseModel):
    pieId: int | None = None
    investedMoney: CardRoundUpMoney | None = None


class CardTransaction(_LooseModel):
    id: int
    transactionToken: str | None = None
    cardId: int | None = None
    clientReferenceId: str | None = None
    amount: float | None = None
    executionAmount: float | None = None
    currencyCode: str | None = None
    status: CardStatus | None = None
    type: CardTransactionType | None = None
    timeCreated: AwareDatetime | None = None
    timeUpdated: AwareDatetime | None = None
    expectedReversalDate: AwareDatetime | None = None
    merchant: CardMerchant | None = None
    isRecurring: bool | None = None
    paymentChannel: str | None = None
    statusReason: str | None = None
    statusReasonParams: dict[str, Any] | None = None
    cardLastFour: str | None = None
    currencyConversion: CardCurrencyConversion | None = None
    atmWithdrawalFee: float | None = None
    t212Cashback: CardCashback | None = None
    partnersCashback: CardCashback | None = None
    roundUp: CardRoundUp | None = None
    billingAmount: float | None = None

    def charged_amount(self) -> float:
        """Amount actually deducted from the card balance.

        ATM withdrawals that carry a fee report ``amount`` inclusive of the
        fee while ``billingAmount`` excludes it (observed in real data:
        amount=100.10, billingAmount=100.00, atmWithdrawalFee=0.10), so the
        larger of the two is the real deduction. Defaults to ``billingAmount``
        and falls back to 0.0 when the API omits both.
        """
        if self.atmWithdrawalFee:
            return self.amount if self.amount is not None else 0.0
        if self.billingAmount is not None:
            return self.billingAmount
        return self.amount if self.amount is not None else 0.0
