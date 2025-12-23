from datetime import datetime, timedelta, timezone

from app.core import config as app_config


def test_register_rejects_weak_password(client):
    res = client.post(
        "/auth/register",
        json={
            "email": "weak@example.com",
            "password": "password",
            "name": "Weak User",
        },
    )
    assert res.status_code == 400
    detail = res.json().get("details")
    assert detail["code"] == "WEAK_PASSWORD"
    assert "uppercase" in detail["violations"]


def test_login_allows_existing_weak_password(client):
    # Default fixture user uses a weak password; ensure login still works.
    res = client.post("/auth/login", json={"email": "test@example.com", "password": "test_password_123"})
    assert res.status_code == 200
    body = res.json()
    assert body["must_change_password"] is False
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_password_expiration_sets_flag_on_login(client, db_session):
    from app.models.user import User

    app_config.settings.PASSWORD_MAX_AGE_DAYS = 1

    user = db_session.query(User).filter(User.email == "test@example.com").first()
    user.password_changed_at = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.add(user)
    db_session.commit()

    res = client.post("/auth/login", json={"email": "test@example.com", "password": "test_password_123"})
    assert res.status_code == 200
    assert res.json()["must_change_password"] is True


def test_password_expiration_reflected_in_me_endpoint(client, users, db_session):
    from app.models.user import User

    app_config.settings.PASSWORD_MAX_AGE_DAYS = 1
    user_a, _ = users
    user_a.password_changed_at = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.add(user_a)
    db_session.commit()

    res = client.get("/users/me")
    assert res.status_code == 200
    assert res.json()["must_change_password"] is True


def test_recent_password_has_no_expiration_flag(client, db_session):
    from app.models.user import User

    app_config.settings.PASSWORD_MAX_AGE_DAYS = 1

    user = db_session.query(User).filter(User.email == "test@example.com").first()
    user.password_changed_at = datetime.now(timezone.utc)
    db_session.add(user)
    db_session.commit()

    res = client.post("/auth/login", json={"email": "test@example.com", "password": "test_password_123"})
    assert res.status_code == 200
    assert res.json()["must_change_password"] is False

