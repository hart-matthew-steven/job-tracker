from __future__ import annotations

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.credit import CreditLedger
from app.models.user import User


class InsufficientCreditsError(Exception):
    pass


@dataclass
class BalanceSummary:
    balance_cents: int
    total_granted_cents: int
    total_spent_cents: int


class CreditsService:
    """
    Helpers around the credit ledger. All arithmetic stays in integer cents and
    the ledger remains the source of truth for both grants and spends.
    """

    MAX_PAGE_SIZE = 200

    def __init__(self, db: Session):
        self.db = db

    def get_balance_cents(self, user_id: int) -> int:
        summary = self.get_balance_summary(user_id)
        return summary.balance_cents

    def get_balance_summary(self, user_id: int) -> BalanceSummary:
        granted = (
            self.db.query(func.coalesce(func.sum(CreditLedger.amount_cents), 0))
            .filter(CreditLedger.user_id == user_id, CreditLedger.amount_cents > 0)
            .scalar()
        )
        spent = (
            self.db.query(func.coalesce(func.sum(CreditLedger.amount_cents), 0))
            .filter(CreditLedger.user_id == user_id, CreditLedger.amount_cents < 0)
            .scalar()
        )
        balance = int((granted or 0) + (spent or 0))
        return BalanceSummary(
            balance_cents=balance,
            total_granted_cents=int(granted or 0),
            total_spent_cents=int(abs(spent or 0)),
        )

    def list_ledger(self, user_id: int, *, limit: int = 50, offset: int = 0) -> list[CreditLedger]:
        normalized_limit = max(1, min(int(limit or 50), self.MAX_PAGE_SIZE))
        normalized_offset = max(0, int(offset or 0))
        return (
            self.db.query(CreditLedger)
            .filter(CreditLedger.user_id == user_id)
            .order_by(CreditLedger.created_at.desc(), CreditLedger.id.desc())
            .offset(normalized_offset)
            .limit(normalized_limit)
            .all()
        )

    def apply_ledger_entry(
        self,
        user_id: int,
        *,
        amount_cents: int,
        source: str,
        idempotency_key: str,
        source_ref: str | None = None,
        description: str | None = None,
        currency: str = "usd",
        pack_key: str | None = None,
        stripe_checkout_session_id: str | None = None,
        stripe_payment_intent_id: str | None = None,
        commit: bool = True,
    ) -> CreditLedger:
        normalized_source = (source or "").strip().lower()
        if not normalized_source:
            raise ValueError("source is required")
        normalized_currency = (currency or "usd").strip().lower() or "usd"
        normalized_ref = source_ref.strip() if isinstance(source_ref, str) and source_ref.strip() else None
        normalized_description = description.strip() if isinstance(description, str) and description.strip() else None
        normalized_idempotency = (idempotency_key or "").strip()
        if not normalized_idempotency:
            raise ValueError("idempotency_key is required")

        existing = (
            self.db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.idempotency_key == normalized_idempotency,
            )
            .first()
        )
        if existing:
            return existing

        entry = CreditLedger(
            user_id=user_id,
            amount_cents=int(amount_cents),
            source=normalized_source,
            source_ref=normalized_ref,
            description=normalized_description,
            currency=normalized_currency,
            pack_key=pack_key.strip() if isinstance(pack_key, str) and pack_key.strip() else None,
            stripe_checkout_session_id=(
                stripe_checkout_session_id.strip()
                if isinstance(stripe_checkout_session_id, str) and stripe_checkout_session_id.strip()
                else None
            ),
            stripe_payment_intent_id=(
                stripe_payment_intent_id.strip()
                if isinstance(stripe_payment_intent_id, str) and stripe_payment_intent_id.strip()
                else None
            ),
            idempotency_key=normalized_idempotency,
        )
        self.db.add(entry)
        if commit:
            self.db.commit()
            self.db.refresh(entry)
        else:
            self.db.flush()
        return entry

    def spend_credits(
        self,
        *,
        user_id: int,
        amount_cents: int,
        reason: str,
        idempotency_key: str,
    ) -> CreditLedger:
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")

        normalized_key = (idempotency_key or "").strip()
        if not normalized_key:
            raise ValueError("idempotency_key is required")

        existing = (
            self.db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.idempotency_key == normalized_key,
            )
            .first()
        )
        if existing:
            return existing

        user_row = (
            self.db.execute(
                select(User).where(User.id == user_id).with_for_update()
            )
            .scalars()
            .first()
        )
        if not user_row:
            raise ValueError("User not found")

        balance = self.get_balance_cents(user_id)
        if balance < amount_cents:
            raise InsufficientCreditsError("Insufficient credits")

        entry = self.apply_ledger_entry(
            user_id,
            amount_cents=-amount_cents,
            source="usage",
            description=reason,
            idempotency_key=normalized_key,
            commit=False,
        )
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def require_credits(
        self,
        *,
        user_id: int,
        amount_cents: int,
        reason: str,
        idempotency_key: str,
    ) -> None:
        try:
            self.spend_credits(
                user_id=user_id,
                amount_cents=amount_cents,
                reason=reason,
                idempotency_key=idempotency_key,
            )
        except InsufficientCreditsError as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient credits",
            ) from exc


def format_cents_to_dollars(value: int) -> str:
    decimal_value = (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{decimal_value:.2f}"
