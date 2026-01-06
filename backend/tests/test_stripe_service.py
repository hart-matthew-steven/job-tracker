from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.core import config as app_config
from app.models.credit import CreditLedger
from app.models.stripe_event import StripeEvent
from app.services.credits import CreditsService
from app.services.stripe import StripeService


class _FakeStripe:
    class error:
        class SignatureVerificationError(Exception):
            pass

    def __init__(self):
        self.created_customers: list[dict] = []
        self.checkout_sessions: list[dict] = []

        fake = self

        class _CustomerAPI:
            def create(self, **kwargs):
                cid = f"cus_{len(fake.created_customers)+1}"
                fake.created_customers.append(kwargs | {"id": cid})
                return {"id": cid}

        class _SessionAPI:
            def create(self, **kwargs):
                sid = f"cs_test_{len(fake.checkout_sessions)+1}"
                session = {
                    "id": sid,
                    "url": "https://example.test/checkout",
                    "metadata": kwargs.get("metadata", {}),
                }
                fake.checkout_sessions.append(session | {"price": kwargs.get("line_items", [{}])[0].get("price")})
                return session

        self.Customer = _CustomerAPI()
        self.checkout = SimpleNamespace(Session=_SessionAPI())
        self.Webhook = SimpleNamespace(construct_event=lambda payload, sig_header, secret: json.loads(payload))


def test_ensure_customer_creates_and_reuses(db_session, users, stripe_packs):
    app_config.settings.STRIPE_SECRET_KEY = "sk_test"
    user, _ = users
    fake = _FakeStripe()
    service = StripeService(db_session, stripe_client=fake)

    customer_id = service.ensure_customer(user)
    assert customer_id.startswith("cus_")
    assert user.stripe_customer_id == customer_id
    assert len(fake.created_customers) == 1

    reused = service.ensure_customer(user)
    assert reused == customer_id
    assert len(fake.created_customers) == 1


def test_create_checkout_session_uses_pack_map(db_session, users, stripe_packs):
    app_config.settings.STRIPE_SECRET_KEY = "sk_test"
    user, _ = users
    fake = _FakeStripe()
    service = StripeService(db_session, stripe_client=fake)

    session = service.create_checkout_session(
        user,
        pack_key="starter",
        success_url="https://example.test/success",
        cancel_url="https://example.test/cancel",
    )

    assert session["metadata"]["pack_key"] == "starter"
    assert session["metadata"]["credits_to_grant"] == str(stripe_packs["starter"].credits)
    assert fake.checkout_sessions[0]["price"] == stripe_packs["starter"].price_id


def _checkout_event(user_id: int, customer_id: str, pack_key: str, credits: int) -> dict:
    return {
        "id": f"evt_{pack_key}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": customer_id,
                "payment_status": "paid",
                "id": f"cs_{pack_key}",
                "metadata": {
                    "user_id": str(user_id),
                    "pack_key": pack_key,
                    "credits_to_grant": str(credits),
                },
            }
        },
    }


def test_process_event_is_idempotent_and_updates_balance(db_session, users, stripe_packs):
    app_config.settings.STRIPE_SECRET_KEY = "sk_test"
    app_config.settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    app_config.settings.STRIPE_DEFAULT_CURRENCY = "usd"

    user, _ = users
    user.stripe_customer_id = "cus_linked"
    db_session.commit()

    service = StripeService(db_session, stripe_client=_FakeStripe())

    event = _checkout_event(user.id, "cus_linked", "starter", stripe_packs["starter"].credits)

    applied = service.process_event(event, raw_payload=event)
    assert applied is True

    balance = CreditsService(db_session).get_balance_cents(user.id)
    assert balance == stripe_packs["starter"].credits
    rows = db_session.query(CreditLedger).all()
    assert len(rows) == 1
    assert rows[0].source_ref == "evt_starter"
    assert rows[0].pack_key == "starter"

    replay = service.process_event(event, raw_payload=event)
    assert replay is False
    assert db_session.query(CreditLedger).count() == 1


def test_process_event_marks_failure_and_does_not_credit(db_session, users, stripe_packs, monkeypatch):
    app_config.settings.STRIPE_SECRET_KEY = "sk_test"
    app_config.settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

    user, _ = users
    user.stripe_customer_id = "cus_linked"
    db_session.commit()

    service = StripeService(db_session, stripe_client=_FakeStripe())
    event = _checkout_event(user.id, "cus_linked", "starter", stripe_packs["starter"].credits)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(CreditsService, "apply_ledger_entry", _boom)

    with pytest.raises(RuntimeError):
        service.process_event(event, raw_payload=event)

    assert db_session.query(CreditLedger).count() == 0
    failure = db_session.query(StripeEvent).filter_by(stripe_event_id="evt_starter").one()
    assert failure.status == "failed"
    assert "boom" in failure.error_message

