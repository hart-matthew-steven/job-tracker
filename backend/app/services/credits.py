from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.credit import CreditLedger


class CreditsService:
    """
    Lightweight CRUD helpers around the credit ledger.

    The service keeps all arithmetic in integer cents and defers presentation
    formatting to the caller.
    """

    MAX_PAGE_SIZE = 200

    def __init__(self, db: Session):
        self.db = db

    def get_balance_cents(self, user_id: int) -> int:
        """Return the user's current credit balance in integer cents."""
        total = (
            self.db.query(func.coalesce(func.sum(CreditLedger.amount_cents), 0))
            .filter(CreditLedger.user_id == user_id)
            .scalar()
        )
        return int(total or 0)

    def list_ledger(self, user_id: int, *, limit: int = 50, offset: int = 0) -> list[CreditLedger]:
        """Return newest-first ledger entries for the user."""
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
        source_ref: str | None = None,
        description: str | None = None,
        currency: str = "usd",
        pack_key: str | None = None,
        stripe_checkout_session_id: str | None = None,
        stripe_payment_intent_id: str | None = None,
        commit: bool = True,
    ) -> CreditLedger:
        """
        Apply a ledger entry, enforcing idempotency on (user_id, source_ref).

        When source_ref is provided and already stored for the user, the existing
        row is returned and no new entry is inserted.
        """
        normalized_source = (source or "").strip().lower()
        if not normalized_source:
            raise ValueError("source is required")

        normalized_currency = (currency or "usd").strip().lower() or "usd"
        normalized_ref = source_ref.strip() if isinstance(source_ref, str) and source_ref.strip() else None
        normalized_description = description.strip() if isinstance(description, str) and description.strip() else None
        cents = int(amount_cents)

        if normalized_ref:
            existing = (
                self.db.query(CreditLedger)
                .filter(
                    CreditLedger.user_id == user_id,
                    CreditLedger.source_ref == normalized_ref,
                )
                .first()
            )
            if existing:
                return existing

        entry = CreditLedger(
            user_id=user_id,
            amount_cents=cents,
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
        )
        self.db.add(entry)
        if commit:
            self.db.commit()
            self.db.refresh(entry)
        else:
            self.db.flush()
        return entry


def format_cents_to_dollars(value: int) -> str:
    """
    Convert integer cents into a fixed 0.00 string without float precision issues.
    """
    decimal_value = (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{decimal_value:.2f}"


