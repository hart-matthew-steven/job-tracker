from __future__ import annotations

from app.core.security import create_email_verification_token


def test_auth_login_unverified_email_is_403(client, db_session, monkeypatch):
    # Avoid any real email delivery.
    from app.routes import auth as auth_routes

    monkeypatch.setattr(auth_routes, "send_email", lambda to_email, subject, body: "msg_test_123")

    email = "unverified@example.com"
    password = "Password_12345"

    res = client.post("/auth/register", json={"email": email, "password": password, "name": "New User"})
    assert res.status_code == 200

    # Not verified yet => login should be blocked
    res2 = client.post("/auth/login", json={"email": email, "password": password})
    assert res2.status_code == 403

    # Verify => login should succeed
    token = create_email_verification_token(email=email)
    res3 = client.get("/auth/verify", params={"token": token})
    assert res3.status_code == 200

    res4 = client.post("/auth/login", json={"email": email, "password": password})
    assert res4.status_code == 200


def test_auth_refresh_rotation_rejects_old_cookie(client, monkeypatch):
    # Avoid any real email delivery.
    from app.routes import auth as auth_routes
    from app.services import refresh_tokens

    monkeypatch.setattr(auth_routes, "send_email", lambda to_email, subject, body: "msg_test_123")

    email = "rotate@example.com"
    password = "Password_12345"

    res = client.post("/auth/register", json={"email": email, "password": password, "name": "New User"})
    assert res.status_code == 200

    token = create_email_verification_token(email=email)
    res2 = client.get("/auth/verify", params={"token": token})
    assert res2.status_code == 200

    res3 = client.post("/auth/login", json={"email": email, "password": password})
    assert res3.status_code == 200

    cookie_key = refresh_tokens.cookie_name()
    old_cookie = client.cookies.get(cookie_key)
    assert isinstance(old_cookie, str) and old_cookie

    # Refresh rotates
    res4 = client.post("/auth/refresh")
    assert res4.status_code == 200
    new_cookie = client.cookies.get(cookie_key)
    assert isinstance(new_cookie, str) and new_cookie
    assert new_cookie != old_cookie

    # Put back the old cookie => should be invalid now
    client.cookies.set(cookie_key, old_cookie, path=refresh_tokens.cookie_path())
    res5 = client.post("/auth/refresh")
    assert res5.status_code == 401


