from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.billing import (
    BillingMeOut,
    CreditLedgerEntryOut,
    CreditPackOut,
    CreditsBalanceOut,
    DebugSpendCreditsIn,
)
from app.services.credits import CreditsService, format_cents_to_dollars

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/credits/balance", response_model=CreditsBalanceOut)
def get_credit_balance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CreditsBalanceOut:
    service = CreditsService(db)
    summary = service.get_balance_summary(user.id)
    return CreditsBalanceOut(
        currency="usd",
        balance_cents=summary.balance_cents,
        balance_dollars=format_cents_to_dollars(summary.balance_cents),
        lifetime_granted_cents=summary.total_granted_cents,
        lifetime_spent_cents=summary.total_spent_cents,
        as_of=datetime.now(timezone.utc),
    )


@router.get("/credits/ledger", response_model=list[CreditLedgerEntryOut])
def get_credit_ledger(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CreditLedgerEntryOut]:
    service = CreditsService(db)
    entries = service.list_ledger(user.id, limit=limit, offset=offset)
    return [
        CreditLedgerEntryOut(
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
        for entry in entries
    ]


@router.get("/me", response_model=BillingMeOut)
def get_billing_overview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillingMeOut:
    service = CreditsService(db)
    balance_cents = service.get_balance_cents(user.id)
    ledger = service.list_ledger(user.id, limit=10, offset=0)
    return BillingMeOut(
        currency="usd",
        balance_cents=balance_cents,
        balance_dollars=format_cents_to_dollars(balance_cents),
        stripe_customer_id=user.stripe_customer_id,
        ledger=[
            CreditLedgerEntryOut(
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
            for entry in ledger
        ],
    )


@router.get("/packs", response_model=list[CreditPackOut])
def list_credit_packs() -> list[CreditPackOut]:
    packs: list[CreditPackOut] = []
    for pack in settings.STRIPE_PRICE_MAP.values():
        packs.append(
            CreditPackOut(
                key=pack.key,
                price_id=pack.price_id,
                credits=pack.credits,
                currency=settings.STRIPE_DEFAULT_CURRENCY,
                display_price_dollars=format_cents_to_dollars(pack.credits),
            )
        )
    return sorted(packs, key=lambda p: p.credits)


@router.post("/credits/debug/spend", status_code=status.HTTP_204_NO_CONTENT)
def debug_spend_credits(
    payload: DebugSpendCreditsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if settings.is_prod or not settings.ENABLE_BILLING_DEBUG_ENDPOINT:
        raise HTTPException(status_code=404, detail="Not found")

    service = CreditsService(db)
    service.require_credits(
        user_id=user.id,
        amount_cents=payload.amount_cents,
        reason=payload.reason,
        idempotency_key=payload.idempotency_key,
    )


