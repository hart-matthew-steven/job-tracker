from __future__ import annotations

from app.services.credits import CreditsService


def seed_credits(service: CreditsService, user_id: int, amount: int = 10_000):
    service.apply_ledger_entry(
        user_id,
        amount_cents=amount,
        source="admin",
        description="Seed",
        idempotency_key=f"seed-{user_id}-{amount}",
    )


def test_ai_demo_success_flow(client, users, db_session):
    user, _ = users
    service = CreditsService(db_session)
    seed_credits(service, user.id, 5_000)

    payload = {
        "idempotency_key": "demo-success",
        "estimated_cost_credits": 1_500,
        "simulate_outcome": "success",
        "actual_cost_credits": 1_200,
    }
    resp = client.post("/ai/demo", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["balance_cents"] == 3_800  # 5_000 - 1_200
    assert len(body["ledger_entries"]) >= 3  # reserve + release + charge


def test_ai_demo_failure_refunds(client, users, db_session):
    user, _ = users
    service = CreditsService(db_session)
    seed_credits(service, user.id, 3_000)

    resp = client.post(
        "/ai/demo",
        json={
            "idempotency_key": "demo-fail",
            "estimated_cost_credits": 1_000,
            "simulate_outcome": "fail",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "refunded"
    assert body["balance_cents"] == 3_000


def test_ai_demo_insufficient_balance(client, users):
    user, _ = users
    resp = client.post(
        "/ai/demo",
        json={
            "idempotency_key": "demo-insufficient",
            "estimated_cost_credits": 1_000,
            "simulate_outcome": "success",
        },
    )
    assert resp.status_code == 402

