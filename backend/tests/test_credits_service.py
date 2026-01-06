from __future__ import annotations

from app.models.credit import CreditLedger
from app.services.credits import CreditsService


def test_apply_entry_idempotent_per_user(db_session, users):
    user_a, user_b = users
    service = CreditsService(db_session)

    first = service.apply_ledger_entry(
        user_a.id,
        amount_cents=1500,
        source="Stripe",
        source_ref="evt_test_123",
        description="Initial purchase",
    )
    duplicate = service.apply_ledger_entry(
        user_a.id,
        amount_cents=2500,
        source="stripe",
        source_ref="evt_test_123",
        description="Should reuse",
    )
    assert duplicate.id == first.id
    assert duplicate.amount_cents == first.amount_cents

    # Different user with same source_ref should still insert a new row.
    other = service.apply_ledger_entry(
        user_b.id,
        amount_cents=500,
        source="stripe",
        source_ref="evt_test_123",
        description="Other user purchase",
    )

    rows = db_session.query(CreditLedger).order_by(CreditLedger.id).all()
    assert len(rows) == 2
    assert rows[0].id == first.id
    assert rows[1].id == other.id


def test_get_balance_and_listing(db_session, users):
    user, _ = users
    service = CreditsService(db_session)

    service.apply_ledger_entry(user.id, amount_cents=10_000, source="admin", description="Seed")
    service.apply_ledger_entry(user.id, amount_cents=-2_500, source="usage", description="AI draft")
    service.apply_ledger_entry(user.id, amount_cents=1_250, source="promo", source_ref="promo-2024")

    balance = service.get_balance_cents(user.id)
    assert balance == 8_750

    entries = service.list_ledger(user.id, limit=2, offset=0)
    assert len(entries) == 2  # pagination respected
    assert entries[0].created_at >= entries[1].created_at


