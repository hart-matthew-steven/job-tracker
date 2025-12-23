from datetime import datetime, timedelta, timezone

from app.models.refresh_token import RefreshToken
from app.services.refresh_tokens import hash_refresh_token


def test_update_and_get_settings(client):
    res = client.put(
        "/users/me/settings",
        json={
            "auto_refresh_seconds": 30,
            "theme": "light",
            "default_jobs_sort": "company_asc",
            "default_jobs_view": "active",
            "data_retention_days": 365,
        },
    )
    assert res.status_code == 200
    assert res.json()["message"] == "Settings updated"

    res2 = client.get("/users/me/settings")
    assert res2.status_code == 200
    s = res2.json()
    assert s["auto_refresh_seconds"] == 30
    assert s["theme"] == "light"
    assert s["default_jobs_sort"] == "company_asc"
    assert s["default_jobs_view"] == "active"
    assert s["data_retention_days"] == 365


def test_change_password_revokes_refresh_tokens(client, db_session):
    # Arrange: create an active refresh token row
    from app.models.user import User

    u = db_session.query(User).filter(User.email == "test@example.com").first()
    assert u is not None

    raw = "raw_refresh_token_for_test"
    rt = RefreshToken(
        user_id=u.id,
        token_hash=hash_refresh_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        revoked_at=None,
    )
    db_session.add(rt)
    db_session.commit()

    # Wrong current password -> 400
    res = client.post("/users/me/change-password", json={"current_password": "wrong", "new_password": "new_password_123"})
    assert res.status_code == 400

    # Correct current password -> 200 and revokes tokens
    res2 = client.post(
        "/users/me/change-password",
        json={"current_password": "test_password_123", "new_password": "NewPassword_123!"},
    )
    assert res2.status_code == 200

    # Refresh token row should be revoked
    row = db_session.query(RefreshToken).filter(RefreshToken.user_id == u.id).first()
    assert row is not None
    assert row.revoked_at is not None


def test_change_password_rejects_weak_password(client, db_session):
    res = client.post(
        "/users/me/change-password",
        json={"current_password": "test_password_123", "new_password": "password"},
    )
    assert res.status_code == 400
    detail = res.json().get("details")
    assert detail["code"] == "WEAK_PASSWORD"
    assert "uppercase" in detail["violations"]


def test_change_password_updates_password_changed_at(client, db_session):
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "test@example.com").first()
    assert user is not None
    before = user.password_changed_at

    res = client.post(
        "/users/me/change-password",
        json={"current_password": "test_password_123", "new_password": "SafePassword_789!"},
    )
    assert res.status_code == 200

    db_session.refresh(user)
    assert user.password_changed_at > before


