from __future__ import annotations


import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import config as app_config
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User
from app.services.email_verification import send_code as service_send_code


@pytest.fixture()
def enable_verification():
    app_config.settings.EMAIL_VERIFICATION_ENABLED = True
    app_config.settings.EMAIL_VERIFICATION_CODE_TTL_SECONDS = 900
    app_config.settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS = 60
    app_config.settings.EMAIL_VERIFICATION_MAX_ATTEMPTS = 3
    yield
    app_config.settings.EMAIL_VERIFICATION_ENABLED = False


def _capture_resend(monkeypatch):
    sent: dict[str, str] = {}

    def _fake_send(*, to_email: str, code: str, expires_minutes: int):
        sent["email"] = to_email
        sent["code"] = code
        sent["expires"] = str(expires_minutes)

    monkeypatch.setattr("app.services.email_verification.send_email_verification_code", _fake_send)
    return sent


def test_send_code_persists_hash_and_respects_cooldown(enable_verification, db_session: Session, users, monkeypatch):
    user, _ = users
    user.is_email_verified = False
    db_session.commit()

    sent = _capture_resend(monkeypatch)

    service_send_code(db_session, user=user)

    record = db_session.query(EmailVerificationCode).filter(EmailVerificationCode.user_id == user.id).one()
    assert len(sent["code"]) == 6
    assert record.code_hash != sent["code"]

    # Cooldown should block immediate resend
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        service_send_code(db_session, user=user)
    assert exc.value.status_code == 429


def test_verification_flow_round_trip(
    enable_verification,
    anonymous_client: TestClient,
    users,
    monkeypatch,
    db_session: Session,
):
    user, _ = users
    user.is_email_verified = False
    db_session.commit()

    sent = _capture_resend(monkeypatch)

    resp = anonymous_client.post("/auth/cognito/verification/send", json={"email": user.email})
    assert resp.status_code == 200

    record = db_session.query(EmailVerificationCode).filter(EmailVerificationCode.user_id == user.id).one()
    assert record.consumed_at is None

    monkeypatch.setattr("app.routes.auth_cognito.cognito_admin_mark_email_verified", lambda **kwargs: None)

    resp = anonymous_client.post(
        "/auth/cognito/verification/confirm",
        json={"email": user.email, "code": sent["code"]},
    )
    assert resp.status_code == 200

    db_session.expire_all()
    fresh_user = db_session.get(User, user.id)
    assert fresh_user.is_email_verified is True
    assert user.email_verified_at is not None


def test_unverified_user_blocked_from_jobs(enable_verification, client: TestClient, db_session: Session, users):
    user, _ = users
    user.is_email_verified = False
    db_session.commit()

    resp = client.get("/jobs")
    assert resp.status_code == 403
    assert resp.json().get("error") == "EMAIL_NOT_VERIFIED"


def test_send_code_without_account_is_noop(enable_verification, anonymous_client: TestClient, db_session: Session):
    resp = anonymous_client.post("/auth/cognito/verification/send", json={"email": "missing@example.test"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "OK"
    assert db_session.query(EmailVerificationCode).count() == 0


def test_confirm_without_account_returns_error(enable_verification, anonymous_client: TestClient):
    resp = anonymous_client.post(
        "/auth/cognito/verification/confirm",
        json={"email": "missing@example.test", "code": "123456"},
    )
    assert resp.status_code == 400

