from __future__ import annotations

from app.models.credit import CreditLedger
from app.services.credits import CreditsService, InsufficientCreditsError


def test_apply_entry_idempotent_per_user(db_session, users):
    user_a, user_b = users
    service = CreditsService(db_session)

    first = service.apply_ledger_entry(
        user_a.id,
        amount_cents=1500,
        source="Stripe",
        source_ref="evt_test_123",
        description="Initial purchase",
        idempotency_key="dep-user-a",
    )
    duplicate = service.apply_ledger_entry(
        user_a.id,
        amount_cents=2500,
        source="stripe",
        source_ref="evt_test_123",
        description="Should reuse",
        idempotency_key="dep-user-a",
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
        idempotency_key="dep-user-b",
    )

    rows = db_session.query(CreditLedger).order_by(CreditLedger.id).all()
    assert len(rows) == 2
    assert rows[0].id == first.id
    assert rows[1].id == other.id


def test_get_balance_and_listing(db_session, users):
    user, _ = users
    service = CreditsService(db_session)

    service.apply_ledger_entry(
        user.id,
        amount_cents=10_000,
        source="admin",
        description="Seed",
        idempotency_key="seed",
    )
    service.apply_ledger_entry(
        user.id,
        amount_cents=-2_500,
        source="usage",
        description="AI draft",
        idempotency_key="usage-draft",
    )
    service.apply_ledger_entry(
        user.id,
        amount_cents=1_250,
        source="promo",
        source_ref="promo-2024",
        idempotency_key="promo-2024",
    )

    balance = service.get_balance_cents(user.id)
    assert balance == 8_750

    entries = service.list_ledger(user.id, limit=2, offset=0)
    assert len(entries) == 2  # pagination respected
    assert entries[0].created_at >= entries[1].created_at


def test_spend_credits_idempotent(db_session, users):
    user, _ = users
    service = CreditsService(db_session)
    service.apply_ledger_entry(
        user.id,
        amount_cents=5_000,
        source="admin",
        description="Seed",
        idempotency_key="seed",
    )

    service.spend_credits(user_id=user.id, amount_cents=1_000, reason="test", idempotency_key="spend-1")
    service.spend_credits(user_id=user.id, amount_cents=1_000, reason="test", idempotency_key="spend-1")

    balance = service.get_balance_cents(user.id)
    assert balance == 4_000


def test_spend_credits_insufficient(db_session, users):
    user, _ = users
    service = CreditsService(db_session)
    service.apply_ledger_entry(
        user.id,
        amount_cents=500,
        source="admin",
        description="Seed",
        idempotency_key="seed",
    )

    try:
        service.spend_credits(user_id=user.id, amount_cents=1_000, reason="too much", idempotency_key="spend-2")
        assert False, "expected InsufficientCreditsError"
    except InsufficientCreditsError:
        pass

    balance = service.get_balance_cents(user.id)
    assert balance == 500


def test_reserve_finalize_and_refund(db_session, users):
    user, _ = users
    service = CreditsService(db_session)
    # seed credits
    service.apply_ledger_entry(
        user.id,
        amount_cents=5_000,
        source="admin",
        description="Seed",
        idempotency_key="seed",
    )

    reservation = service.reserve_credits(
        user_id=user.id,
        amount_cents=2_000,
        idempotency_key="reserve-1",
        description="demo reserve",
    )
    assert reservation.reservation.entry_type == "ai_reserve"
    assert service.get_balance_cents(user.id) == 3_000

    # finalize with smaller actual cost
    result = service.finalize_charge(
        reservation_id=reservation.reservation.id,
        user_id=user.id,
        actual_amount_cents=1_500,
        idempotency_key="finalize-1",
    )
    assert len(result.entries) == 2
    assert service.get_balance_cents(user.id) == 3_500  # 500 released back, 1500 charged

    # refund after finalize should fail
    try:
        service.refund_reservation(
            reservation_id=reservation.reservation.id,
            user_id=user.id,
            idempotency_key="refund-ignored",
            reason="should not refund",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_reservation_refund_flow(db_session, users):
    user, _ = users
    service = CreditsService(db_session)
    service.apply_ledger_entry(
        user.id,
        amount_cents=3_000,
        source="admin",
        description="Seed",
        idempotency_key="seed-rr",
    )

    reservation = service.reserve_credits(
        user_id=user.id,
        amount_cents=1_000,
        idempotency_key="reserve-rr",
    )
    refund = service.refund_reservation(
        reservation_id=reservation.reservation.id,
        user_id=user.id,
        idempotency_key="refund-rr",
    )
    assert len(refund.entries) == 1
    assert refund.entries[0].entry_type == "ai_refund"
    assert service.get_balance_cents(user.id) == 3_000


def test_reservation_insufficient_balance(db_session, users):
    user, _ = users
    service = CreditsService(db_session)
    service.apply_ledger_entry(
        user.id,
        amount_cents=400,
        source="admin",
        description="Seed",
        idempotency_key="seed-small",
    )

    try:
        service.reserve_credits(
            user_id=user.id,
            amount_cents=500,
            idempotency_key="reserve-too-high",
        )
        assert False, "expected InsufficientCreditsError"
    except InsufficientCreditsError:
        pass


def test_reservation_idempotency(db_session, users):
    user, _ = users
    service = CreditsService(db_session)
    service.apply_ledger_entry(
        user.id,
        amount_cents=1_000,
        source="admin",
        description="Seed",
        idempotency_key="seed-idem",
    )

    first = service.reserve_credits(
        user_id=user.id,
        amount_cents=500,
        idempotency_key="reserve-idem",
    )
    second = service.reserve_credits(
        user_id=user.id,
        amount_cents=500,
        idempotency_key="reserve-idem",
    )
    assert first.reservation.id == second.reservation.id
    assert service.get_balance_cents(user.id) == 500


