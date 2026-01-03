from __future__ import annotations

from app.core import config as app_config


def _create_job(client):
    res = client.post(
        "/jobs/",
        json={"company_name": "Acme", "job_title": "Engineer", "location": None, "job_url": None, "tags": []},
    )
    assert res.status_code == 200
    return res.json()


def test_document_confirm_upload_then_download_blocked_until_clean(client):
    job = _create_job(client)

    # Presign creates a pending document
    res = client.post(
        f"/jobs/{job['id']}/documents/presign-upload",
        json={"doc_type": "resume", "filename": "resume.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert res.status_code == 200
    doc = res.json()["document"]
    assert doc["status"] == "pending"

    # Confirm upload moves to scanning (head_object stub returns ContentLength=123)
    res2 = client.post(
        f"/jobs/{job['id']}/documents/confirm-upload",
        json={"document_id": doc["id"]},
    )
    assert res2.status_code == 200
    doc2 = res2.json()
    assert doc2["status"] == "scanning"
    assert doc2["size_bytes"] == 123

    # Download should be blocked while scanning
    res3 = client.get(f"/jobs/{job['id']}/documents/{doc['id']}/presign-download")
    assert res3.status_code == 409


def test_document_scan_result_clean_allows_download(client):
    job = _create_job(client)

    res = client.post(
        f"/jobs/{job['id']}/documents/presign-upload",
        json={"doc_type": "resume", "filename": "resume.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert res.status_code == 200
    doc = res.json()["document"]

    res2 = client.post(
        f"/jobs/{job['id']}/documents/confirm-upload",
        json={"document_id": doc["id"]},
    )
    assert res2.status_code == 200

    # Scan result endpoint requires shared secret
    app_config.settings.GUARD_DUTY_ENABLED = True
    app_config.settings.DOC_SCAN_SHARED_SECRET = "scan_secret"

    res3 = client.post(
        f"/jobs/{job['id']}/documents/{doc['id']}/scan-result",
        headers={"x-scan-secret": "scan_secret"},
        json={"document_id": doc["id"], "result": "clean"},
    )
    assert res3.status_code == 200
    assert res3.json()["ok"] is True

    # Now download should succeed (presigned URL is stubbed)
    res4 = client.get(f"/jobs/{job['id']}/documents/{doc['id']}/presign-download")
    assert res4.status_code == 200
    assert "download_url" in res4.json()


def test_document_scan_result_unauthorized(client):
    job = _create_job(client)
    app_config.settings.GUARD_DUTY_ENABLED = True
    app_config.settings.DOC_SCAN_SHARED_SECRET = "scan_secret"

    res = client.post(
        f"/jobs/{job['id']}/documents/999/scan-result",
        headers={"x-scan-secret": "wrong"},
        json={"document_id": 999, "result": "clean"},
    )
    assert res.status_code == 401


