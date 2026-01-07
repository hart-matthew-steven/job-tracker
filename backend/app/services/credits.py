from __future__ import annotations

import uuid
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


@dataclass
class CreditReservation:
    reservation: CreditLedger
    correlation_id: str


@dataclass
class LedgerOperationResult:
    entries: list[CreditLedger]


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

    def _lock_user(self, user_id: int) -> User:
        user = (
            self.db.execute(select(User).where(User.id == user_id).with_for_update())
            .scalars()
            .first()
        )
        if not user:
            raise ValueError("User not found")
        return user

    def _find_entry_by_idempotency(self, user_id: int, key: str) -> CreditLedger | None:
        return (
            self.db.query(CreditLedger)
            .filter(CreditLedger.user_id == user_id, CreditLedger.idempotency_key == key)
            .first()
        )

    def apply_ledger_entry(
        self,
        user_id: int,
        *,
        amount_cents: int,
        source: str,
        idempotency_key: str,
        entry_type: str = "credit_purchase",
        status: str = "posted",
        correlation_id: str | None = None,
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

        existing = self._find_entry_by_idempotency(user_id, normalized_idempotency)
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
            entry_type=entry_type,
            status=status,
            correlation_id=correlation_id,
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

        existing = self._find_entry_by_idempotency(user_id, normalized_key)
        if existing:
            return existing

        self._lock_user(user_id)
        balance = self.get_balance_cents(user_id)
        if balance < amount_cents:
            raise InsufficientCreditsError("Insufficient credits")

        entry = self.apply_ledger_entry(
            user_id,
            amount_cents=-amount_cents,
            source="usage",
            description=reason,
            idempotency_key=normalized_key,
            entry_type="ai_charge",
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

    # --- Reservation helpers ---

    def reserve_credits(
        self,
        *,
        user_id: int,
        amount_cents: int,
        idempotency_key: str,
        correlation_id: str | None = None,
        description: str | None = None,
    ) -> CreditReservation:
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")

        normalized_key = (idempotency_key or "").strip()
        if not normalized_key:
            raise ValueError("idempotency_key is required")

        existing = self._find_entry_by_idempotency(user_id, normalized_key)
        if existing:
            correlation = existing.correlation_id or str(existing.id)
            return CreditReservation(reservation=existing, correlation_id=correlation)

        self._lock_user(user_id)
        balance = self.get_balance_cents(user_id)
        if balance < amount_cents:
            raise InsufficientCreditsError("Insufficient credits")

        correlation = correlation_id or str(uuid.uuid4())
        entry = self.apply_ledger_entry(
            user_id,
            amount_cents=-amount_cents,
            source="usage",
            description=description or "AI reservation",
            idempotency_key=normalized_key,
            entry_type="ai_reserve",
            status="reserved",
            correlation_id=correlation,
            commit=False,
        )
        self.db.commit()
        self.db.refresh(entry)
        return CreditReservation(reservation=entry, correlation_id=correlation)

    def finalize_charge(
        self,
        *,
        reservation_id: int,
        user_id: int,
        actual_amount_cents: int | None,
        idempotency_key: str,
    ) -> LedgerOperationResult:
        if actual_amount_cents is not None and actual_amount_cents <= 0:
            raise ValueError("actual_amount_cents must be positive")

        reservation = (
            self.db.query(CreditLedger)
            .filter(
                CreditLedger.id == reservation_id,
                CreditLedger.user_id == user_id,
                CreditLedger.entry_type == "ai_reserve",
            )
            .with_for_update()
            .first()
        )
        if not reservation:
            raise ValueError("Reservation not found")

        if reservation.status in {"finalized", "refunded"}:
            entries = (
                self.db.query(CreditLedger)
                .filter(
                    CreditLedger.correlation_id == reservation.correlation_id,
                    CreditLedger.entry_type.in_(["ai_release", "ai_charge"]),
                )
                .order_by(CreditLedger.id.asc())
                .all()
            )
            return LedgerOperationResult(entries=entries)

        reserved = abs(reservation.amount_cents)
        actual = actual_amount_cents or reserved
        if actual > reserved:
            raise ValueError("actual_amount_cents cannot exceed reserved amount")

        release_key = f"{idempotency_key}::release"

        release_entry = self.apply_ledger_entry(
            user_id,
            amount_cents=reserved,
            source="usage",
            description="AI reservation release",
            idempotency_key=release_key,
            entry_type="ai_release",
            status="posted",
            correlation_id=reservation.correlation_id,
            commit=False,
        )
        charge_entry = self.apply_ledger_entry(
            user_id,
            amount_cents=-actual,
            source="usage",
            description="AI usage charge",
            idempotency_key=idempotency_key,
            entry_type="ai_charge",
            status="posted",
            correlation_id=reservation.correlation_id,
            commit=False,
        )
        reservation.status = "finalized"
        self.db.commit()
        return LedgerOperationResult(entries=[release_entry, charge_entry])

    def refund_reservation(
        self,
        *,
        reservation_id: int,
        user_id: int,
        idempotency_key: str,
        reason: str | None = None,
    ) -> LedgerOperationResult:
        reservation = (
            self.db.query(CreditLedger)
            .filter(
                CreditLedger.id == reservation_id,
                CreditLedger.user_id == user_id,
                CreditLedger.entry_type == "ai_reserve",
            )
            .with_for_update()
            .first()
        )
        if not reservation:
            raise ValueError("Reservation not found")

        if reservation.status == "finalized":
            raise ValueError("Reservation already finalized")

        if reservation.status == "refunded":
            entries = (
                self.db.query(CreditLedger)
                .filter(
                    CreditLedger.correlation_id == reservation.correlation_id,
                    CreditLedger.entry_type == "ai_refund",
                )
                .all()
            )
            return LedgerOperationResult(entries=entries)

        refund_entry = self.apply_ledger_entry(
            user_id,
            amount_cents=abs(reservation.amount_cents),
            source="usage",
            description=reason or "AI reservation refund",
            idempotency_key=idempotency_key,
            entry_type="ai_refund",
            status="posted",
            correlation_id=reservation.correlation_id,
            commit=False,
        )
        reservation.status = "refunded"
        self.db.commit()
        return LedgerOperationResult(entries=[refund_entry])


def format_cents_to_dollars(value: int) -> str:
    decimal_value = (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{decimal_value:.2f}"
