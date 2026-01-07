from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.billing import AiDemoRequest, AiDemoResponse, CreditLedgerEntryOut
from app.services.credits import CreditsService, InsufficientCreditsError

router = APIRouter(prefix="/ai", tags=["ai-demo"])


def _to_schema(entry) -> CreditLedgerEntryOut:
    return CreditLedgerEntryOut(
        amount_cents=entry.amount_cents,
        source=entry.source,
        description=entry.description,
        created_at=entry.created_at,
        source_ref=entry.source_ref,
        pack_key=entry.pack_key,
        stripe_checkout_session_id=entry.stripe_checkout_session_id,
        stripe_payment_intent_id=entry.stripe_payment_intent_id,
        idempotency_key=entry.idempotency_key,
        entry_type=entry.entry_type,
        status=entry.status,
        correlation_id=entry.correlation_id,
    )


@router.post("/demo", response_model=AiDemoResponse)
def simulate_ai_usage(
    payload: AiDemoRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AiDemoResponse:
    service = CreditsService(db)

    try:
        reservation = service.reserve_credits(
            user_id=user.id,
            amount_cents=payload.estimated_cost_credits,
            idempotency_key=f"{payload.idempotency_key}::reserve",
            description="AI demo reservation",
        )
    except InsufficientCreditsError:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    entries = [reservation.reservation]

    if payload.simulate_outcome == "success":
        actual = payload.actual_cost_credits or payload.estimated_cost_credits
        final = service.finalize_charge(
            reservation_id=reservation.reservation.id,
            user_id=user.id,
            actual_amount_cents=actual,
            idempotency_key=f"{payload.idempotency_key}::finalize",
        )
        entries.extend(final.entries)
        status = "success"
    else:
        refund = service.refund_reservation(
            reservation_id=reservation.reservation.id,
            user_id=user.id,
            idempotency_key=f"{payload.idempotency_key}::refund",
            reason="AI demo failure",
        )
        entries.extend(refund.entries)
        status = "refunded"

    balance = service.get_balance_cents(user.id)
    return AiDemoResponse(
        reservation_id=reservation.reservation.id,
        correlation_id=reservation.correlation_id,
        status=status,
        balance_cents=balance,
        ledger_entries=[_to_schema(e) for e in entries],
    )

