from __future__ import annotations

def _create_job(client):
    res = client.post(
        "/jobs/",
        json={"company_name": "Acme", "job_title": "Engineer", "location": None, "job_url": None, "tags": []},
    )
    assert res.status_code == 200
    return res.json()


def _assert_error_shape(res, *, error: str | None = None):
    data = res.json()
    assert isinstance(data, dict)
    assert isinstance(data.get("error"), str) and data["error"]
    assert isinstance(data.get("message"), str) and data["message"]
    if error is not None:
        assert data["error"] == error


def test_error_shape_401_missing_token(anonymous_client):
    res = anonymous_client.get("/jobs")
    assert res.status_code == 401
    _assert_error_shape(res, error="UNAUTHORIZED")


def test_error_shape_404_job_not_found(client):
    res = client.get("/jobs/999999")
    assert res.status_code == 404
    _assert_error_shape(res, error="NOT_FOUND")


def test_error_shape_409_saved_view_duplicate_name(client):
    res1 = client.post("/saved-views/", json={"name": "My View", "data": {"q": "acme"}})
    assert res1.status_code == 201
    res2 = client.post("/saved-views/", json={"name": "My View", "data": {"q": "x"}})
    assert res2.status_code == 409
    _assert_error_shape(res2, error="CONFLICT")


def test_error_shape_422_request_validation_error(client):
    job = _create_job(client)
    res = client.post(
        f"/jobs/{job['id']}/documents/presign-upload",
        json={"doc_type": "bad", "filename": "x.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert res.status_code == 422
    _assert_error_shape(res, error="VALIDATION_ERROR")
    body = res.json()
    assert isinstance(body.get("details"), dict)
    assert isinstance(body["details"].get("errors"), list)




