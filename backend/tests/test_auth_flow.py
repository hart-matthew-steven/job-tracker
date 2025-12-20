from __future__ import annotations

from app.core.security import create_email_verification_token


def test_auth_register_verify_login_refresh_logout(client, db_session, monkeypatch):
    # Avoid any real email delivery.
    from app.routes import auth as auth_routes

    monkeypatch.setattr(auth_routes, "send_email", lambda to_email, subject, body: "msg_test_123")

    email = "newuser@example.com"
    password = "Password_12345"

    res = client.post("/auth/register", json={"email": email, "password": password, "name": "New User"})
    assert res.status_code == 200

    # User exists but not verified yet
    from app.models.user import User

    u = db_session.query(User).filter(User.email == email).first()
    assert u is not None
    assert u.is_email_verified is False

    # Verify
    token = create_email_verification_token(email=email)
    res2 = client.get("/auth/verify", params={"token": token})
    assert res2.status_code == 200

    u2 = db_session.query(User).filter(User.email == email).first()
    assert u2 is not None
    assert u2.is_email_verified is True

    # Login should set refresh cookie and return access token
    res3 = client.post("/auth/login", json={"email": email, "password": password})
    assert res3.status_code == 200
    body = res3.json()
    assert isinstance(body.get("access_token"), str) and body["access_token"]
    assert "set-cookie" in {k.lower() for k in res3.headers.keys()}

    # Refresh should rotate and return a new access token
    res4 = client.post("/auth/refresh")
    assert res4.status_code == 200
    body2 = res4.json()
    assert isinstance(body2.get("access_token"), str) and body2["access_token"]

    # Logout clears cookie
    res5 = client.post("/auth/logout")
    assert res5.status_code == 200
    assert res5.json()["message"] == "Logged out"


def test_auth_refresh_missing_cookie_is_401(client):
    # Clear cookies for this client session
    client.cookies.clear()
    res = client.post("/auth/refresh")
    assert res.status_code == 401


