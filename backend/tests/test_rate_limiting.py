from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.core import config as app_config
from app.core.security import hash_password
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job_application import JobApplication


@pytest.mark.usefixtures("_stub_s3")
def test_rate_limiting_returns_429_when_enabled(db_session):
    """
    Enable SlowAPI rate limiting and assert endpoints return 429 after exceeding limit.

    Note: rate limit decorators are applied at import time, so we reload the app + routes
    after toggling settings.ENABLE_RATE_LIMITING.
    """
    import app.core.rate_limit as rate_limit
    import app.routes.documents as documents_routes
    import app.main as main

    # IMPORTANT:
    # SlowAPI decorators bind at import time. This test reloads modules with rate limiting enabled.
    # We MUST restore module state at the end so other tests don't inherit rate-limited routes.
    try:
        app_config.settings.ENABLE_RATE_LIMITING = True
        app_config.settings.MAX_PENDING_UPLOADS_PER_JOB = 1000

        # To make this test deterministic, we:
        # 1) reload app.core.rate_limit to get a *fresh* limiter instance
        # 2) reload routes + app so decorators/handlers bind to the new limiter
        importlib.reload(rate_limit)
        importlib.reload(documents_routes)
        importlib.reload(main)

        app = main.app

        # Create user + job
        user = User(
            email="rl@example.com",
            name="Rate Limit User",
            password_hash=hash_password("test_password_123"),
            is_active=True,
            is_email_verified=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        job = JobApplication(company_name="Acme", job_title="Engineer", location=None, job_url=None, user_id=user.id)
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: user

        with TestClient(app) as client:
            payload = {
                "doc_type": "thank_you",
                "filename": "a.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1,
            }

            # Limit is 10/minute on presign-upload: first 10 ok, 11th blocked.
            statuses: list[int] = []
            for _ in range(11):
                r = client.post(f"/jobs/{job.id}/documents/presign-upload", json=payload)
                statuses.append(r.status_code)

            assert statuses[:10] == [200] * 10, statuses
            assert statuses[10] == 429, statuses
            r2 = r
            body = r2.json()
            assert body.get("error") == "RATE_LIMITED"
            assert isinstance(body.get("message"), str) and body["message"]
    finally:
        # Restore global config and module bindings for the rest of the test suite.
        app_config.settings.ENABLE_RATE_LIMITING = False
        importlib.reload(rate_limit)
        importlib.reload(documents_routes)
        importlib.reload(main)


