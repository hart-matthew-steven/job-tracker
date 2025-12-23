import os
from datetime import datetime, timezone

# Ensure JWT_SECRET exists before importing app.main (it calls require_jwt_secret() at import time).
os.environ.setdefault("JWT_SECRET", "test_jwt_secret")

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import importlib

from app.core.base import Base
from app.core import config as app_config
from app.core.security import hash_password

# Import models so they register with SQLAlchemy metadata.
from app.models.user import User  # noqa: F401
from app.models.job_application import JobApplication  # noqa: F401
from app.models.job_application_note import JobApplicationNote  # noqa: F401
from app.models.job_application_tag import JobApplicationTag  # noqa: F401
from app.models.job_document import JobDocument  # noqa: F401
from app.models.job_activity import JobActivity  # noqa: F401
from app.models.job_interview import JobInterview  # noqa: F401
from app.models.saved_view import SavedView  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401

from app.core.database import get_db
from app.dependencies.auth import get_current_user


@pytest.fixture(scope="session")
def db_engine():
    # In-memory SQLite for fast, isolated tests.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    # Important: because we use an in-memory SQLite DB with StaticPool, the DB
    # persists across tests. Reset schema per test to avoid cross-test coupling.
    Base.metadata.drop_all(bind=db_engine)
    Base.metadata.create_all(bind=db_engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _stub_s3(monkeypatch):
    """
    Stub S3 client used by app.services.s3 so tests never require AWS creds/network.
    """
    from app.services import s3 as s3_service

    class FakeS3Client:
        def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):  # noqa: N803
            key = Params.get("Key", "")
            return f"https://example.invalid/presigned/{ClientMethod}?key={key}"

        def delete_object(self, Bucket, Key):  # noqa: N803
            return {"ok": True}

        def head_object(self, Bucket, Key):  # noqa: N803
            return {"ContentLength": 123}

    monkeypatch.setattr(s3_service, "_client", lambda: FakeS3Client())
    app_config.settings.S3_BUCKET_NAME = app_config.settings.S3_BUCKET_NAME or "test-bucket"
    app_config.settings.AWS_REGION = app_config.settings.AWS_REGION or "us-east-1"


@pytest.fixture(autouse=True)
def _reset_mutable_settings():
    """
    Tests sometimes tweak global settings (app_config.settings.*). Because that object is
    process-global, we must restore values after each test to avoid cross-test coupling.
    """
    keys = [
        "MAX_UPLOAD_BYTES",
        "MAX_PENDING_UPLOADS_PER_JOB",
        "DOC_SCAN_SHARED_SECRET",
        "ENABLE_RATE_LIMITING",
        "PASSWORD_MIN_LENGTH",
        "PASSWORD_MAX_AGE_DAYS",
    ]
    original = {k: getattr(app_config.settings, k) for k in keys}
    try:
        yield
    finally:
        for k, v in original.items():
            setattr(app_config.settings, k, v)
        # Default all tests to "rate limiting disabled" unless a test explicitly reloads routes with it enabled.
        app_config.settings.ENABLE_RATE_LIMITING = False


@pytest.fixture()
def app(db_session):
    # Ensure settings has a JWT secret even if imported earlier.
    app_config.settings.JWT_SECRET = app_config.settings.JWT_SECRET or "test_jwt_secret"
    # Default to disabled for the general test suite.
    app_config.settings.ENABLE_RATE_LIMITING = False

    # IMPORTANT:
    # SlowAPI decorators bind at import time, so we reload the routes + app with rate limiting disabled
    # to avoid cross-test contamination (the rate limiting test reloads modules with it enabled).
    import app.routes.documents as documents_routes
    import app.main as main

    importlib.reload(documents_routes)
    importlib.reload(main)
    fastapi_app = main.app

    def override_get_db():
        yield db_session
    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def users(db_session):
    """
    Two distinct active, verified users for ownership / isolation tests.
    """
    user_a = User(
        email="test@example.com",
        name="Test User",
        password_hash=hash_password("test_password_123"),
        is_active=True,
        is_email_verified=True,
        password_changed_at=datetime.now(timezone.utc),
    )
    user_b = User(
        email="other@example.com",
        name="Other User",
        password_hash=hash_password("test_password_123"),
        is_active=True,
        is_email_verified=True,
        password_changed_at=datetime.now(timezone.utc),
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)
    return user_a, user_b


@pytest.fixture()
def client(app, users):
    """
    Default client authenticated as user_a.
    """
    user_a, _ = users
    app.dependency_overrides[get_current_user] = lambda: user_a
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client_for(app):
    """
    Context manager to create a client authenticated as an arbitrary user.

    Usage:
        with client_for(user) as c:
            ...
    """

    @contextmanager
    def _client_for(user: User):
        app.dependency_overrides[get_current_user] = lambda: user
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.pop(get_current_user, None)

    return _client_for


