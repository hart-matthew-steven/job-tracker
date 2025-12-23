from __future__ import annotations

from app.core import config as app_config


def _create_job(client):
    res = client.post(
        "/jobs/",
        json={"company_name": "Acme", "job_title": "Engineer", "location": None, "job_url": None, "tags": []},
    )
    assert res.status_code == 200
    return res.json()


def _create_doc(client, job_id: int):
    res = client.post(
        f"/jobs/{job_id}/documents/presign-upload",
        json={"doc_type": "resume", "filename": "resume.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert res.status_code == 200
    return res.json()["document"]


def test_internal_scan_result_requires_secret(client):
    app_config.settings.GUARD_DUTY_ENABLED = True
    app_config.settings.DOC_SCAN_SHARED_SECRET = "scan_secret"

    job = _create_job(client)
    doc = _create_doc(client, job["id"])

    # Missing token -> 401
    res = client.post(
        f"/internal/documents/{doc['id']}/scan-result",
        json={"result": "CLEAN"},
    )
    assert res.status_code == 401

    # Wrong token -> 401
    res2 = client.post(
        f"/internal/documents/{doc['id']}/scan-result",
        headers={"x-internal-token": "wrong"},
        json={"result": "CLEAN"},
    )
    assert res2.status_code == 401


def test_internal_scan_result_clean_then_idempotent(client):
    app_config.settings.GUARD_DUTY_ENABLED = True
    app_config.settings.DOC_SCAN_SHARED_SECRET = "scan_secret"

    job = _create_job(client)
    doc = _create_doc(client, job["id"])

    # Clean -> uploaded + scan_status CLEAN
    res = client.post(
        f"/internal/documents/{doc['id']}/scan-result",
        headers={"x-internal-token": "scan_secret"},
        json={"result": "CLEAN", "scan_message": "ok"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["scan_status"] == "CLEAN"

    # Second call should be a no-op (still CLEAN)
    res2 = client.post(
        f"/internal/documents/{doc['id']}/scan-result",
        headers={"x-internal-token": "scan_secret"},
        json={"result": "INFECTED", "scan_message": "should_ignore"},
    )
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["scan_status"] == "CLEAN"


def test_internal_scan_result_infected_keeps_db_row_and_allows_quarantine_key_fill(client):
    app_config.settings.GUARD_DUTY_ENABLED = True
    app_config.settings.DOC_SCAN_SHARED_SECRET = "scan_secret"

    job = _create_job(client)
    doc = _create_doc(client, job["id"])

    res = client.post(
        f"/internal/documents/{doc['id']}/scan-result",
        headers={"x-internal-token": "scan_secret"},
        json={"result": "INFECTED", "scan_message": "eicar", "quarantined_s3_key": "q/prefix/file"},
    )
    assert res.status_code == 200
    assert res.json()["scan_status"] == "INFECTED"

    # Row still exists on list endpoint (we do NOT delete DB row when infected)
    res_list = client.get(f"/jobs/{job['id']}/documents")
    assert res_list.status_code == 200
    docs = res_list.json()
    found = next((d for d in docs if d["id"] == doc["id"]), None)
    assert found is not None
    assert found["status"] == "infected"
    assert found["scan_status"] == "INFECTED"
    assert found["quarantined_s3_key"] == "q/prefix/file"


def test_internal_scan_result_truncates_overlong_scan_message(client):
    app_config.settings.GUARD_DUTY_ENABLED = True
    app_config.settings.DOC_SCAN_SHARED_SECRET = "scan_secret"

    job = _create_job(client)
    doc = _create_doc(client, job["id"])

    long_msg = "x" * 5000
    res = client.post(
        f"/internal/documents/{doc['id']}/scan-result",
        headers={"x-internal-token": "scan_secret"},
        json={"result": "ERROR", "scan_message": long_msg},
    )
    assert res.status_code == 200

    res_list = client.get(f"/jobs/{job['id']}/documents")
    assert res_list.status_code == 200
    docs = res_list.json()
    found = next((d for d in docs if d["id"] == doc["id"]), None)
    assert found is not None
    assert found["scan_status"] == "ERROR"
    assert found["status"] == "failed"
    assert isinstance(found.get("scan_message"), str)
    assert len(found["scan_message"]) <= 1024


