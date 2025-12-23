from __future__ import annotations

import importlib

import pytest

from app.core import config as app_config
from app.models.job_application import JobApplication
from app.models.job_document import JobDocument
from app.services import email as email_service


def test_email_module_imports_without_provider_env(monkeypatch):
    global email_service
    monkeypatch.setattr(app_config.settings, "EMAIL_ENABLED", False)
    monkeypatch.setattr(app_config.settings, "RESEND_API_KEY", "")
    email_service = importlib.reload(email_service)


def test_send_email_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config.settings, "EMAIL_ENABLED", False)
    monkeypatch.setattr(app_config.settings, "EMAIL_PROVIDER", "resend")

    called = {"count": 0}

    def _fake_resend(*args, **kwargs):
        called["count"] += 1

    monkeypatch.setattr(email_service, "_send_email_resend", _fake_resend)
    email_service.send_email("to@example.com", "Subject", "Body")
    assert called["count"] == 0


def test_send_email_enabled_missing_config(monkeypatch):
    monkeypatch.setattr(app_config.settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(app_config.settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(app_config.settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(app_config.settings, "FROM_EMAIL", "")

    with pytest.raises(email_service.EmailNotConfiguredError):
        email_service.send_email("to@example.com", "Subject", "Body")


def _create_job_and_document(db_session, user_id: int) -> tuple[JobApplication, JobDocument]:
    job = JobApplication(
        user_id=user_id,
        company_name="Acme",
        job_title="Engineer",
        status="applied",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    doc = JobDocument(
        application_id=job.id,
        doc_type="resume",
        s3_key="uploads/test-key",
        original_filename="resume.pdf",
        content_type="application/pdf",
        status="pending",
        scan_status="PENDING",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return job, doc


def test_guard_duty_disabled_scan_result_noop(client, db_session, users, monkeypatch):
    user_a, _ = users
    job, doc = _create_job_and_document(db_session, user_a.id)

    monkeypatch.setattr(app_config.settings, "GUARD_DUTY_ENABLED", False)
    monkeypatch.setattr(app_config.settings, "DOC_SCAN_SHARED_SECRET", "")

    res = client.post(
        f"/jobs/{job.id}/documents/scan-result",
        json={"document_id": doc.id, "result": "clean"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["guard_duty_enabled"] is False


def test_guard_duty_enabled_missing_secret_errors(client, db_session, users, monkeypatch):
    user_a, _ = users
    job, doc = _create_job_and_document(db_session, user_a.id)

    monkeypatch.setattr(app_config.settings, "GUARD_DUTY_ENABLED", True)
    monkeypatch.setattr(app_config.settings, "DOC_SCAN_SHARED_SECRET", "")

    res = client.post(
        f"/jobs/{job.id}/documents/scan-result",
        json={"document_id": doc.id, "result": "clean"},
    )
    assert res.status_code == 500
    assert "DOC_SCAN_SHARED_SECRET" in res.json()["message"]

