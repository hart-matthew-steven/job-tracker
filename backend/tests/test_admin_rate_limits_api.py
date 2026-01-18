from __future__ import annotations

from contextlib import contextmanager


from app.routes import admin_rate_limits as admin_routes
from app.services.rate_limit_admin import RateLimitRecord


class _FakeAdminService:
    def __init__(self):
        self.overrides_called_with: dict | None = None

    def list_user_limits(self, *, user_id: int, now: int | None = None):
        return [
            RateLimitRecord(
                limiter_key="route:ai_chat:window:60",
                window_seconds=60,
                limit=10,
                count=2,
                remaining=8,
                expires_at=999,
                record_type="counter",
            )
        ]

    def reset_user_limits(self, *, user_id: int) -> int:
        return 3

    def apply_override(self, *, user_id: int, limit: int, window_seconds: int, ttl_seconds: int, now: int | None = None):
        self.overrides_called_with = {
            "user_id": user_id,
            "limit": limit,
            "window_seconds": window_seconds,
            "ttl_seconds": ttl_seconds,
        }
        return 1234


@contextmanager
def _override_admin_service(fake: _FakeAdminService, client):
    app = client.app
    previous = app.dependency_overrides.get(admin_routes.get_rate_limit_admin_service)
    app.dependency_overrides[admin_routes.get_rate_limit_admin_service] = lambda: fake
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(admin_routes.get_rate_limit_admin_service, None)
        else:
            app.dependency_overrides[admin_routes.get_rate_limit_admin_service] = previous


def test_admin_routes_require_authentication(anonymous_client):
    resp = anonymous_client.get("/admin/rate-limits/status", params={"user_id": 1})
    assert resp.status_code == 401


def test_admin_routes_require_admin_user(client):
    resp = client.get("/admin/rate-limits/status", params={"user_id": 1})
    assert resp.status_code == 403


def test_status_endpoint_returns_records_for_admin(db_session, client_for, users):
    admin, _ = users
    admin.is_admin = True
    db_session.commit()

    fake_service = _FakeAdminService()
    with client_for(admin) as admin_client, _override_admin_service(fake_service, admin_client):
        resp = admin_client.get("/admin/rate-limits/status", params={"user_id": admin.id})

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == admin.id
    assert body["records"][0]["limiter_key"] == "route:ai_chat:window:60"


def test_reset_endpoint_returns_deleted_count(db_session, client_for, users):
    admin, _ = users
    admin.is_admin = True
    db_session.commit()

    fake_service = _FakeAdminService()
    with client_for(admin) as admin_client, _override_admin_service(fake_service, admin_client):
        resp = admin_client.post("/admin/rate-limits/reset", json={"user_id": admin.id})

    assert resp.status_code == 200
    assert resp.json()["deleted"] == 3


def test_override_endpoint_applies_override(db_session, client_for, users):
    admin, _ = users
    admin.is_admin = True
    db_session.commit()

    fake_service = _FakeAdminService()
    payload = {"user_id": admin.id, "limit": 50, "window_seconds": 30, "ttl_seconds": 300}
    with client_for(admin) as admin_client, _override_admin_service(fake_service, admin_client):
        resp = admin_client.post("/admin/rate-limits/override", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 50
    assert fake_service.overrides_called_with == payload
