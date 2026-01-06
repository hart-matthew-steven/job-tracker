from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.credit import CreditLedger


def seed_ledger(db_session, user_id: int) -> None:
    now = datetime.now(timezone.utc)
    entries = [
        CreditLedger(
            user_id=user_id,
            amount_cents=5_000,
            source="admin",
            description="Manual top-up",
            created_at=now - timedelta(days=2),
        ),
        CreditLedger(
            user_id=user_id,
            amount_cents=-1_500,
            source="usage",
            description="Cover letter generation",
            source_ref="usage-1",
            created_at=now - timedelta(days=1),
        ),
        CreditLedger(
            user_id=user_id,
            amount_cents=2_000,
            source="promo",
            description="Launch bonus",
            source_ref="promo-jan",
            created_at=now,
        ),
    ]
    db_session.add_all(entries)
    db_session.commit()


def test_get_balance_authorized(client, db_session, users):
    user, other = users
    seed_ledger(db_session, user.id)
    # Noise for other user should not affect the balance.
    db_session.add(
        CreditLedger(
            user_id=other.id,
            amount_cents=9_999,
            source="admin",
        )
    )
    db_session.commit()

    resp = client.get("/billing/credits/balance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["currency"] == "usd"
    assert body["balance_cents"] == 5_500
    assert body["balance_dollars"] == "55.00"


def test_get_balance_requires_auth(anonymous_client):
    resp = anonymous_client.get("/billing/credits/balance")
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"


def test_get_ledger_authorized(client, db_session, users):
    user, _ = users
    seed_ledger(db_session, user.id)

    resp = client.get("/billing/credits/ledger?limit=2&offset=0")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) == 2
    assert rows[0]["source"] == "promo"  # newest first
    assert rows[0]["source_ref"] == "promo-jan"
    assert rows[1]["source"] == "usage"


def test_get_ledger_requires_auth(anonymous_client):
    resp = anonymous_client.get("/billing/credits/ledger")
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"


def test_get_billing_overview(client, db_session, users):
    user, _ = users
    user.stripe_customer_id = "cus_abc"
    seed_ledger(db_session, user.id)

    resp = client.get("/billing/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["balance_cents"] == 5_500
    assert data["stripe_customer_id"] == "cus_abc"
    assert len(data["ledger"]) == 3


def test_list_packs_requires_no_auth(stripe_packs, anonymous_client):
    resp = anonymous_client.get("/billing/packs")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and data
    keys = [p["key"] for p in data]
    expected_order = [pack.key for pack in sorted(stripe_packs.values(), key=lambda p: p.credits)]
    assert keys == expected_order
