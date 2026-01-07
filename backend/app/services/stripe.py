from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

try:  # pragma: no cover - dependency presence is validated at runtime
    import stripe  # type: ignore
except ImportError:  # pragma: no cover
    stripe = None  # type: ignore
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.stripe_event import StripeEvent, StripeEventStatus
from app.models.user import User
from app.services.credits import CreditsService

logger = logging.getLogger(__name__)

MAX_ERROR_MESSAGE_LENGTH = 500


class StripeServiceError(Exception):
    """Base error for Stripe service operations."""


class StripeWebhookError(StripeServiceError):
    """Raised when a webhook payload cannot be verified."""


class StripeService:
    """
    Stripe integration facade. All direct Stripe SDK calls live here.

    Responsibilities:
    - Manage customers tied to application users
    - Create checkout sessions for purchasing prepaid credits
    - Persist webhook payloads for auditing
    - Convert successful payments into credit ledger entries exactly once
    """

    def __init__(self, db: Session, stripe_client: Any | None = None):
        self.db = db
        self.currency = settings.STRIPE_DEFAULT_CURRENCY or "usd"
        self.stripe = stripe_client or stripe
        if self.stripe is not None and settings.STRIPE_SECRET_KEY:
            self.stripe.api_key = settings.STRIPE_SECRET_KEY

    # ------------------------------------------------------------------
    # Checkout creation
    # ------------------------------------------------------------------
    def ensure_customer(self, user: User) -> str:
        """Create or reuse the Stripe customer id stored on the user."""
        if not settings.STRIPE_SECRET_KEY:
            raise StripeServiceError("Stripe secret key is not configured")
        stripe_client = self._require_sdk()

        db_user = self.db.get(User, user.id)
        if not db_user:
            raise StripeServiceError("User not found in session")

        if db_user.stripe_customer_id:
            return db_user.stripe_customer_id

        customer = stripe_client.Customer.create(
            email=user.email,
            name=user.name,
            metadata={"user_id": str(user.id)},
        )
        customer_id = customer.get("id")
        if not customer_id:
            raise StripeServiceError("Stripe did not return a customer id")
        db_user.stripe_customer_id = customer_id
        self.db.commit()
        self.db.refresh(db_user)
        logger.info("Linked user %s to Stripe customer %s", user.id, customer_id)
        return customer_id

    def create_checkout_session(
        self,
        user: User,
        *,
        pack_key: str,
        success_url: str,
        cancel_url: str,
    ) -> Any:
        """Create a Stripe Checkout Session for purchasing credits."""
        pack = settings.get_stripe_pack(pack_key)
        if not pack:
            raise StripeServiceError(f"Unknown pack: {pack_key}")

        customer_id = self.ensure_customer(user)
        logger.info(
            "Creating Stripe checkout session: user=%s customer=%s pack=%s",
            user.id,
            customer_id,
            pack.key,
        )
        stripe_client = self._require_sdk()
        metadata = {
            "user_id": str(user.id),
            "pack_key": pack.key,
            "credits_to_grant": str(pack.credits),
            "environment": settings.ENV,
        }
        return stripe_client.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            success_url=success_url,
            cancel_url=cancel_url,
            line_items=[
                {
                    "price": pack.price_id,
                    "quantity": 1,
                }
            ],
            metadata=metadata,
            payment_intent_data={
                "metadata": metadata,
            },
        )

    # ------------------------------------------------------------------
    # Webhook handling
    # ------------------------------------------------------------------
    def parse_event(self, payload: bytes, signature: str | None) -> Any:
        """Validate webhook signature and deserialize the event."""
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise StripeWebhookError("Stripe webhook secret is not configured")
        if not signature:
            raise StripeWebhookError("Missing Stripe-Signature header")
        stripe_client = self._require_sdk()
        try:
            return stripe_client.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except self.stripe.error.SignatureVerificationError as exc:
            raise StripeWebhookError(f"Invalid Stripe signature: {exc}") from exc

    def process_event(self, event: Any, raw_payload: dict[str, Any]) -> bool:
        """
        Persist the incoming event and invoke handlers once per Stripe id.

        Returns True if credits were applied, False if the event was already processed
        or does not affect credit balances.
        """
        event_id = event.get("id")
        event_type = event.get("type")
        if not event_id or not event_type:
            raise StripeServiceError("Stripe event missing id/type")

        created = self._ensure_event_record(event_id, event_type, raw_payload)
        if not created:
            logger.info("Stripe event %s already processed; skipping", event_id)
            return False

        try:
            with self.db.begin():
                handled = self._dispatch_event(event)
                status = StripeEventStatus.PROCESSED if handled else StripeEventStatus.SKIPPED
                self._update_event_status(event_id, status, error=None)
            return handled
        except Exception as exc:
            logger.exception("Stripe event %s failed: %s", event_id, exc)
            self._mark_event_failed(event_id, exc)
            raise

    def _ensure_event_record(self, event_id: str, event_type: str, payload: dict[str, Any]) -> bool:
        record = StripeEvent(
            stripe_event_id=event_id,
            event_type=event_type,
            payload=payload,
            status=StripeEventStatus.PENDING.value,
        )
        try:
            self.db.add(record)
            self.db.commit()
            return True
        except IntegrityError as exc:
            self.db.rollback()
            if self._is_unique_violation(exc):
                return False
            raise
        finally:
            if record in self.db:
                self.db.expunge(record)

    def _dispatch_event(self, event: Any) -> bool:
        event_type = event.get("type")
        if event_type == "checkout.session.completed":
            return self._handle_checkout_session(event)
        logger.info("Ignoring unsupported Stripe event type: %s", event_type)
        return False

    def _handle_checkout_session(self, event: Any) -> bool:
        session = (event.get("data") or {}).get("object") or {}
        if session.get("payment_status") != "paid":
            logger.info(
                "Checkout session %s not paid (status=%s); skipping",
                session.get("id"),
                session.get("payment_status"),
            )
            return False

        metadata = session.get("metadata") or {}
        user_id_raw = metadata.get("user_id")
        pack_key = metadata.get("pack_key")
        credits_raw = metadata.get("credits_to_grant")
        if not user_id_raw or not pack_key or credits_raw is None:
            raise StripeServiceError("Checkout session missing required metadata")

        pack = settings.get_stripe_pack(pack_key)
        if not pack:
            raise StripeServiceError(f"Unknown pack key on checkout metadata: {pack_key}")

        try:
            user_id = int(user_id_raw)
            credits_to_grant = int(credits_raw)
        except ValueError as exc:
            raise StripeServiceError("Checkout session metadata malformed") from exc

        if credits_to_grant != pack.credits:
            raise StripeServiceError("Checkout metadata credits mismatch configured pack")

        user = self.db.get(User, user_id)
        if not user:
            raise StripeServiceError(f"User {user_id} not found for Stripe metadata")

        customer_id = session.get("customer")
        if user.stripe_customer_id and customer_id and user.stripe_customer_id != customer_id:
            raise StripeServiceError(
                f"Stripe customer mismatch for user {user.id}: {customer_id} != {user.stripe_customer_id}"
            )

        description = f"Stripe Checkout {session.get('id')} ({pack.key})"
        credits_service = CreditsService(self.db)
        credits_service.apply_ledger_entry(
            user.id,
            amount_cents=credits_to_grant,
            source="stripe",
            idempotency_key=f"{event.get('id')}-deposit",
            source_ref=event.get("id"),
            description=description,
            currency=self.currency,
            pack_key=pack.key,
            stripe_checkout_session_id=session.get("id"),
            stripe_payment_intent_id=session.get("payment_intent"),
            commit=False,
        )
        return True

    def _update_event_status(
        self,
        event_id: str,
        status: StripeEventStatus,
        error: str | None,
    ) -> None:
        record = (
            self.db.query(StripeEvent)
            .filter(StripeEvent.stripe_event_id == event_id)
            .with_for_update()
            .first()
        )
        if not record:
            return
        record.status = status.value
        record.error_message = (error or "")[:MAX_ERROR_MESSAGE_LENGTH] if error else None
        record.processed_at = self._now()

    def _mark_event_failed(self, event_id: str, exc: Exception) -> None:
        message = str(exc)
        with self.db.begin():
            record = (
                self.db.query(StripeEvent)
                .filter(StripeEvent.stripe_event_id == event_id)
                .with_for_update()
                .first()
            )
            if not record:
                return
            record.status = StripeEventStatus.FAILED.value
            record.error_message = message[:MAX_ERROR_MESSAGE_LENGTH]
            record.processed_at = self._now()

    def _is_unique_violation(self, exc: IntegrityError) -> bool:
        orig = getattr(exc, "orig", None)
        pgcode = getattr(orig, "pgcode", None)
        if pgcode == "23505":
            return True
        message = str(orig or exc)
        return "stripe_events_stripe_event_id_key" in message or "UNIQUE constraint failed: stripe_events.stripe_event_id" in message

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _require_sdk(self):
        if self.stripe is None:
            raise StripeServiceError("Stripe SDK is not installed")
        return self.stripe


def parse_raw_payload(payload: bytes) -> dict[str, Any]:
    """
    Deserialize the raw webhook payload as JSON for StripeEvent auditing.
    """
    try:
        text = payload.decode("utf-8")
        return json.loads(text)
    except Exception as exc:
        logger.error("Unable to parse Stripe payload: %s", exc)
        return {}


