from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import importlib

from app.core.base import Base
from app.core import config as app_config

# Import models so they register with SQLAlchemy metadata.
from app.models.user import User  # noqa: F401
from app.models.job_application import JobApplication  # noqa: F401
from app.models.job_application_note import JobApplicationNote  # noqa: F401
from app.models.job_application_tag import JobApplicationTag  # noqa: F401
from app.models.job_document import JobDocument  # noqa: F401
from app.models.job_activity import JobActivity  # noqa: F401
from app.models.job_interview import JobInterview  # noqa: F401
from app.models.saved_view import SavedView  # noqa: F401

from app.core.database import get_db


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
        "GUARD_DUTY_ENABLED",
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
def app(db_session, monkeypatch):
    # Ensure required Cognito settings exist for tests.
    app_config.settings.COGNITO_REGION = app_config.settings.COGNITO_REGION or "us-east-1"
    app_config.settings.COGNITO_USER_POOL_ID = app_config.settings.COGNITO_USER_POOL_ID or "local-test-pool"
    app_config.settings.COGNITO_APP_CLIENT_ID = app_config.settings.COGNITO_APP_CLIENT_ID or "test-client-id"
    app_config.settings.COGNITO_JWKS_CACHE_SECONDS = 60
    app_config.settings.ENABLE_RATE_LIMITING = False

    # SlowAPI decorators bind at import time, so reload routes with latest settings.
    import app.routes.documents as documents_routes
    import app.main as main

    importlib.reload(documents_routes)
    importlib.reload(main)
    fastapi_app = main.app

    def override_get_db():
        yield db_session
    fastapi_app.dependency_overrides[get_db] = override_get_db

    # Stub Cognito verification + profile lookups so tests do not call AWS.
    from app.auth import cognito as cognito_module
    from app.services import cognito_client as cognito_service

    class _FakeVerifyError(cognito_module.CognitoInvalidTokenError):
        pass

    def _fake_verify(token: str):
        if not token.startswith("test-sub:"):
            raise _FakeVerifyError("invalid token")
        sub = token.split("test-sub:", 1)[1]
        return {
            "sub": sub,
            "token_use": "access",
            "client_id": app_config.settings.COGNITO_APP_CLIENT_ID,
            "iss": "https://example.invalid/local",
            "email": f"{sub}@example.test",
        }

    def _fake_get_user(access_token: str):
        sub = access_token.split("test-sub:", 1)[1] if "test-sub:" in access_token else "unknown"
        return {
            "sub": sub,
            "email": f"{sub}@example.test",
            "name": "Test User",
            "Username": sub,
        }

    monkeypatch.setattr(cognito_module, "verify_cognito_jwt", _fake_verify)
    monkeypatch.setattr(cognito_service, "cognito_get_user", _fake_get_user)

    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def users(db_session):
    """
    Two distinct active Cognito-backed users for ownership / isolation tests.
    """
    user_a = User(
        email="sub-test-user@example.test",
        name="Test User",
        cognito_sub="sub-test-user",
        auth_provider="cognito",
        is_active=True,
    )
    user_b = User(
        email="sub-other-user@example.test",
        name="Other User",
        cognito_sub="sub-other-user",
        auth_provider="cognito",
        is_active=True,
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
    headers = {"Authorization": f"Bearer test-sub:{user_a.cognito_sub}"}
    with TestClient(app, headers=headers) as c:
        yield c


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
        headers = {"Authorization": f"Bearer test-sub:{user.cognito_sub}"}
        with TestClient(app, headers=headers) as c:
            yield c

    return _client_for


@pytest.fixture()
def anonymous_client(app):
    """Client without Authorization header (for testing 401 responses)."""
    with TestClient(app) as c:
        yield c


