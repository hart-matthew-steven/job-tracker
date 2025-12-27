from __future__ import annotations

from app.services.email_verification import issue_email_verification_token
from app.models.user import User


def _create_job(client):
    res = client.post(
        "/jobs/",
        json={"company_name": "Acme", "job_title": "Engineer", "location": None, "job_url": None, "tags": []},
    )
    assert res.status_code == 200
    return res.json()


def _assert_error_shape(res, *, error: str | None = None):
    data = res.json()
    assert isinstance(data, dict)
    assert isinstance(data.get("error"), str) and data["error"]
    assert isinstance(data.get("message"), str) and data["message"]
    if error is not None:
        assert data["error"] == error


def test_error_shape_401_refresh_missing_cookie(client):
    client.cookies.clear()
    res = client.post("/auth/refresh")
    assert res.status_code == 401
    _assert_error_shape(res, error="UNAUTHORIZED")


def test_error_shape_404_job_not_found(client):
    res = client.get("/jobs/999999")
    assert res.status_code == 404
    _assert_error_shape(res, error="NOT_FOUND")


def test_error_shape_409_saved_view_duplicate_name(client):
    res1 = client.post("/saved-views/", json={"name": "My View", "data": {"q": "acme"}})
    assert res1.status_code == 201
    res2 = client.post("/saved-views/", json={"name": "My View", "data": {"q": "x"}})
    assert res2.status_code == 409
    _assert_error_shape(res2, error="CONFLICT")


def test_error_shape_422_request_validation_error(client):
    job = _create_job(client)
    res = client.post(
        f"/jobs/{job['id']}/documents/presign-upload",
        json={"doc_type": "bad", "filename": "x.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert res.status_code == 422
    _assert_error_shape(res, error="VALIDATION_ERROR")
    body = res.json()
    assert isinstance(body.get("details"), dict)
    assert isinstance(body["details"].get("errors"), list)


def test_error_shape_403_login_unverified_email(client, db_session, monkeypatch):
    # Avoid any real email delivery.
    from app.routes import auth as auth_routes

    monkeypatch.setattr(auth_routes, "send_email", lambda to_email, subject, body: "msg_test_123")

    email = "unverified2@example.com"
    password = "Password_12345"

    res = client.post("/auth/register", json={"email": email, "password": password, "name": "New User"})
    assert res.status_code == 200

    res2 = client.post("/auth/login", json={"email": email, "password": password})
    assert res2.status_code == 403
    _assert_error_shape(res2, error="FORBIDDEN")

    # Verify so this test doesn't interfere with later auth tests that might re-use email.
    user = db_session.query(User).filter(User.email == email).first()
    token = issue_email_verification_token(db_session, user)
    db_session.commit()
    res3 = client.get("/auth/verify", params={"token": token})
    assert res3.status_code == 200


