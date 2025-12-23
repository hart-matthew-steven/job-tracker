from __future__ import annotations

from app.core import config as app_config


def _create_job(client):
    res = client.post(
        "/jobs/",
        json={"company_name": "Acme", "job_title": "Engineer", "location": None, "job_url": None, "tags": []},
    )
    assert res.status_code == 200
    return res.json()


def test_single_doc_type_replaces_existing_db_row(client):
    job = _create_job(client)

    res1 = client.post(
        f"/jobs/{job['id']}/documents/presign-upload",
        json={"doc_type": "resume", "filename": "resume1.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert res1.status_code == 200
    # doc1 is implicitly replaced; keep the response call to validate the shape.
    _ = res1.json()["document"]

    res2 = client.post(
        f"/jobs/{job['id']}/documents/presign-upload",
        json={"doc_type": "resume", "filename": "resume2.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert res2.status_code == 200
    doc2 = res2.json()["document"]
    # SQLite may reuse integer PKs after delete; don't assert on id inequality.
    assert doc2["doc_type"] == "resume"
    assert doc2["original_filename"] == "resume2.pdf"

    res_list = client.get(f"/jobs/{job['id']}/documents")
    assert res_list.status_code == 200
    docs = res_list.json()
    assert isinstance(docs, list)
    assert len(docs) == 1
    assert docs[0]["doc_type"] == "resume"
    assert docs[0]["original_filename"] == "resume2.pdf"


def test_confirm_upload_returns_409_when_s3_head_missing(client, monkeypatch):
    # Force head_object to fail so confirm-upload returns a 409.
    # NOTE: app.routes.documents imports head_object into its own module namespace,
    # so patching app.services.s3.head_object won't affect the router.
    from app.routes import documents as documents_routes

    monkeypatch.setattr(
        documents_routes,
        "head_object",
        lambda s3_key: (_ for _ in ()).throw(RuntimeError("missing")),
    )

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
    assert res2.status_code == 409


def test_confirm_upload_twice_is_409(client):
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

    res3 = client.post(
        f"/jobs/{job['id']}/documents/confirm-upload",
        json={"document_id": doc["id"]},
    )
    assert res3.status_code == 409


def test_infected_scan_blocks_download_and_sets_status(client):
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

    app_config.settings.GUARD_DUTY_ENABLED = True
    app_config.settings.DOC_SCAN_SHARED_SECRET = "scan_secret"
    res3 = client.post(
        f"/jobs/{job['id']}/documents/scan-result",
        headers={"x-scan-secret": "scan_secret"},
        json={"document_id": doc["id"], "result": "infected"},
    )
    assert res3.status_code == 200
    assert res3.json()["status"] == "infected"

    res_list = client.get(f"/jobs/{job['id']}/documents")
    assert res_list.status_code == 200
    docs = res_list.json()
    assert docs and docs[0]["id"] == doc["id"]
    assert docs[0]["status"] == "infected"

    # Download remains blocked while not uploaded.
    res_dl = client.get(f"/jobs/{job['id']}/documents/{doc['id']}/presign-download")
    assert res_dl.status_code == 409


