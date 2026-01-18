from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.billing import StripeCheckoutCreate, StripeCheckoutOut
from app.services.stripe import StripeService, StripeServiceError, StripeWebhookError, parse_raw_payload

router = APIRouter(prefix="/billing/stripe", tags=["billing"])


@router.post("/checkout", response_model=StripeCheckoutOut)
def create_checkout_session(
    payload: StripeCheckoutCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StripeCheckoutOut:
    service = StripeService(db)
    frontend_base = (settings.FRONTEND_BASE_URL or "http://localhost:5173").rstrip("/")
    success_url = f"{frontend_base}/billing/stripe/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{frontend_base}/billing/stripe/cancelled"
    try:
        session = service.create_checkout_session(
            user,
            pack_key=payload.pack_key,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except StripeServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    metadata = session.get("metadata") or {}
    pack_key = metadata.get("pack_key") or payload.pack_key
    pack = settings.get_stripe_pack(pack_key) if pack_key else None
    credits = int(metadata.get("credits_to_grant") or (pack.credits if pack else 0))
    return StripeCheckoutOut(
        checkout_session_id=session.get("id"),
        checkout_url=session.get("url"),
        currency=service.currency,
        pack_key=pack_key,
        credits_granted=credits,
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    service = StripeService(db)
    raw_payload = parse_raw_payload(payload)
    try:
        event = service.parse_event(payload, signature)
        credits_applied = service.process_event(event, raw_payload)
    except StripeWebhookError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except StripeServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return {"received": True, "credits_applied": credits_applied}


