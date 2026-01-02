from __future__ import annotations

from app.core import config as app_config
from app.models.job_application import JobApplication
from app.models.job_document import JobDocument


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
        f"/jobs/{job.id}/documents/{doc.id}/scan-result",
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
        f"/jobs/{job.id}/documents/{doc.id}/scan-result",
        json={"document_id": doc.id, "result": "clean"},
    )
    assert res.status_code == 500
    assert "DOC_SCAN_SHARED_SECRET" in res.json()["message"]

