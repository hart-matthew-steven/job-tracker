from app.core import config as app_config
from app.models.job_document import JobDocument


def _create_job(client):
    res = client.post(
        "/jobs/",
        json={"company_name": "Acme", "job_title": "Engineer", "location": None, "job_url": None, "tags": []},
    )
    assert res.status_code == 200
    return res.json()


def test_documents_presign_rejects_invalid_doc_type(client):
    job = _create_job(client)
    res = client.post(
        f"/jobs/{job['id']}/documents/presign-upload",
        json={"doc_type": "bad", "filename": "x.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    # doc_type is a Literal in the schema, so FastAPI rejects invalid values at validation time.
    assert res.status_code == 422


def test_documents_presign_rejects_too_large(client):
    job = _create_job(client)
    app_config.settings.MAX_UPLOAD_BYTES = 5
    res = client.post(
        f"/jobs/{job['id']}/documents/presign-upload",
        json={"doc_type": "resume", "filename": "x.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert res.status_code == 413


def test_documents_presign_pending_limit(client, db_session):
    job = _create_job(client)
    app_config.settings.MAX_PENDING_UPLOADS_PER_JOB = 1

    # Seed an existing pending doc
    db_session.add(
        JobDocument(
            application_id=job["id"],
            doc_type="resume",
            s3_key="k",
            original_filename="a.pdf",
            content_type="application/pdf",
            size_bytes=1,
            status="pending",
        )
    )
    db_session.commit()

    res = client.post(
        f"/jobs/{job['id']}/documents/presign-upload",
        json={"doc_type": "job_description", "filename": "b.pdf", "content_type": "application/pdf", "size_bytes": 1},
    )
    assert res.status_code == 429


