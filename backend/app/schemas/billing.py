from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class CreditsBalanceOut(BaseModel):
    currency: str = "usd"
    balance_cents: int
    balance_dollars: str
    lifetime_granted_cents: int
    lifetime_spent_cents: int
    as_of: datetime


class CreditLedgerEntryOut(BaseModel):
    amount_cents: int
    source: str
    description: str | None = None
    created_at: datetime
    source_ref: str | None = None
    pack_key: str | None = None
    stripe_checkout_session_id: str | None = None
    stripe_payment_intent_id: str | None = None
    idempotency_key: str


class StripeCheckoutCreate(BaseModel):
    pack_key: str

    @field_validator("pack_key")
    @staticmethod
    def _validate_pack_key(value: str) -> str:
        normalized = (value or "").strip().lower()
        if not normalized:
            raise ValueError("pack_key is required")
        return normalized


class StripeCheckoutOut(BaseModel):
    checkout_session_id: str
    checkout_url: str
    currency: str
    pack_key: str
    credits_granted: int


class CreditPackOut(BaseModel):
    key: str
    price_id: str
    credits: int
    currency: str
    display_price_dollars: str


class BillingMeOut(BaseModel):
    currency: str
    balance_cents: int
    balance_dollars: str
    stripe_customer_id: str | None
    ledger: list[CreditLedgerEntryOut]


class DebugSpendCreditsIn(BaseModel):
    amount_cents: int
    reason: str
    idempotency_key: str

    @field_validator("amount_cents")
    @staticmethod
    def _validate_amount(value: int) -> int:
        if value <= 0:
            raise ValueError("amount_cents must be positive")
        return value

