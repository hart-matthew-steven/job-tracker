from __future__ import annotations

from app.services.email_verification import issue_email_verification_token


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
    from app.models.user import User

    user = db_session.query(User).filter(User.email == email).first()
    token = issue_email_verification_token(db_session, user)
    db_session.commit()
    res3 = client.get("/auth/verify", params={"token": token})
    assert res3.status_code == 200

    res4 = client.post("/auth/login", json={"email": email, "password": password})
    assert res4.status_code == 200


def test_auth_refresh_rotation_rejects_old_cookie(client, db_session, monkeypatch):
    # Avoid any real email delivery.
    from app.routes import auth as auth_routes
    from app.services import refresh_tokens

    monkeypatch.setattr(auth_routes, "send_email", lambda to_email, subject, body: "msg_test_123")

    email = "rotate@example.com"
    password = "Password_12345"

    res = client.post("/auth/register", json={"email": email, "password": password, "name": "New User"})
    assert res.status_code == 200

    from app.models.user import User

    user = db_session.query(User).filter(User.email == email).first()
    token = issue_email_verification_token(db_session, user)
    db_session.commit()
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


def test_access_token_invalid_after_token_version_change(app, db_session, monkeypatch):
    from fastapi.testclient import TestClient
    from app.routes import auth as auth_routes
    from app.models.user import User
    from app.services.email_verification import issue_email_verification_token

    monkeypatch.setattr(auth_routes, "send_email", lambda *args, **kwargs: "msg_test_123")

    email = "tokenver@example.com"
    password = "Password_12345"

    with TestClient(app) as http:
        res = http.post("/auth/register", json={"email": email, "password": password, "name": "Token Ver"})
        assert res.status_code == 200

        user = db_session.query(User).filter(User.email == email).first()
        token = issue_email_verification_token(db_session, user)
        db_session.commit()

        verify_res = http.get("/auth/verify", params={"token": token})
        assert verify_res.status_code == 200

        login_res = http.post("/auth/login", json={"email": email, "password": password})
        assert login_res.status_code == 200
        access_token = login_res.json()["access_token"]

    # Bump token_version simulating forced logout (e.g., admin action)
    user.token_version = int(user.token_version or 0) + 1
    db_session.add(user)
    db_session.commit()

    with TestClient(app) as http:
        res_me = http.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
        assert res_me.status_code == 401


