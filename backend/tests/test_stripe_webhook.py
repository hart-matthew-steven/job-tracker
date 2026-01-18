from __future__ import annotations

import json

from app.core import config as app_config
from app.models.credit import CreditLedger
from app.services import stripe as stripe_module
from app.services.stripe import StripeServiceError, StripeWebhookError


def _event_payload(user_id: int, customer_id: str, pack_key: str, credits: int, event_id: str = "evt_test") -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": customer_id,
                "payment_status": "paid",
                "id": "cs_test_123",
                "metadata": {
                    "user_id": str(user_id),
                    "pack_key": pack_key,
                    "credits_to_grant": str(credits),
                },
            }
        },
    }


def test_webhook_valid_signature_applies_credit(client, db_session, users, stripe_packs, monkeypatch):
    app_config.settings.STRIPE_SECRET_KEY = "sk_test"
    app_config.settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

    user, _ = users
    user.stripe_customer_id = "cus_valid"
    db_session.commit()

    event = _event_payload(user.id, "cus_valid", "starter", stripe_packs["starter"].credits, "evt_valid")
    payload_bytes = json.dumps(event).encode("utf-8")

    def _fake_parse(self, payload, signature):
        assert signature == "valid"
        return event

    monkeypatch.setattr(stripe_module.StripeService, "parse_event", _fake_parse, raising=False)

    resp = client.post(
        "/billing/stripe/webhook",
        content=payload_bytes,
        headers={"stripe-signature": "valid"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"received": True, "credits_applied": True}

    ledger_rows = db_session.query(CreditLedger).all()
    assert len(ledger_rows) == 1
    assert ledger_rows[0].source_ref == "evt_valid"
    assert ledger_rows[0].amount_cents == stripe_packs["starter"].credits


def test_webhook_invalid_signature_rejected(client, monkeypatch):
    app_config.settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

    def _fake_parse(self, payload, signature):
        raise StripeWebhookError("bad signature")

    monkeypatch.setattr(stripe_module.StripeService, "parse_event", _fake_parse, raising=False)

    resp = client.post(
        "/billing/stripe/webhook",
        content=b"{}",
        headers={"stripe-signature": "invalid"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "VALIDATION_ERROR"


def test_webhook_duplicate_event_ignored(client, db_session, users, stripe_packs, monkeypatch):
    app_config.settings.STRIPE_SECRET_KEY = "sk_test"
    app_config.settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

    user, _ = users
    user.stripe_customer_id = "cus_dupe"
    db_session.commit()

    event = _event_payload(user.id, "cus_dupe", "starter", stripe_packs["starter"].credits, "evt_dupe")
    payload_bytes = json.dumps(event).encode("utf-8")

    def _fake_parse(self, payload, signature):
        return event

    monkeypatch.setattr(stripe_module.StripeService, "parse_event", _fake_parse, raising=False)

    first = client.post("/billing/stripe/webhook", content=payload_bytes, headers={"stripe-signature": "ignored"})
    assert first.status_code == 200
    assert first.json()["credits_applied"] is True

    again = client.post("/billing/stripe/webhook", content=payload_bytes, headers={"stripe-signature": "ignored"})
    assert again.status_code == 200
    assert again.json()["credits_applied"] is False

    ledger_rows = db_session.query(CreditLedger).all()
    assert len(ledger_rows) == 1


def test_webhook_is_public_endpoint(anonymous_client, monkeypatch):
    app_config.settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

    def _fake_parse(self, payload, signature):
        return {"id": "evt_public", "type": "checkout.session.completed", "data": {"object": {}}}

    def _fake_process(self, event, raw_payload):
        return True

    monkeypatch.setattr(stripe_module.StripeService, "parse_event", _fake_parse, raising=False)
    monkeypatch.setattr(stripe_module.StripeService, "process_event", _fake_process, raising=False)

    resp = anonymous_client.post(
        "/billing/stripe/webhook",
        content=b"{}",
        headers={"stripe-signature": "valid"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"received": True, "credits_applied": True}


def test_webhook_processing_error_returns_500(client, monkeypatch):
    app_config.settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

    event = {"id": "evt_fail", "type": "checkout.session.completed"}

    def _fake_parse(self, payload, signature):
        return event

    def _fake_process(self, event, raw_payload):
        raise StripeServiceError("processing failed")

    monkeypatch.setattr(stripe_module.StripeService, "parse_event", _fake_parse, raising=False)
    monkeypatch.setattr(stripe_module.StripeService, "process_event", _fake_process, raising=False)

    resp = client.post(
        "/billing/stripe/webhook",
        content=b"{}",
        headers={"stripe-signature": "valid"},
    )
    assert resp.status_code == 500

