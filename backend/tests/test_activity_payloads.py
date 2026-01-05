from __future__ import annotations


def _activity_items(client, job_id: int):
    res = client.get(f"/jobs/{job_id}/activity")
    assert res.status_code == 200
    payload = res.json()
    assert isinstance(payload, dict)
    return payload.get("items") or []


def test_status_changed_payload_and_normalization(client):
    # Create job with default status "applied"
    res = client.post(
        "/jobs/",
        json={"company_name": "Acme", "job_title": "Engineer", "location": None, "job_url": None, "tags": []},
    )
    assert res.status_code == 200
    job = res.json()

    # Setting status to same value (with whitespace/case changes) should NOT log an event.
    res2 = client.patch(f"/jobs/{job['id']}", json={"status": "  Applied  "})
    assert res2.status_code == 200
    assert res2.json()["status"] == "applied"

    res3_items = _activity_items(client, job["id"])
    assert all(ev["type"] != "status_changed" for ev in res3_items)

    # Changing status should log with from/to and normalized "to".
    res4 = client.patch(f"/jobs/{job['id']}", json={"status": "  Interviewing  "})
    assert res4.status_code == 200
    assert res4.json()["status"] == "interviewing"

    events = _activity_items(client, job["id"])
    ev = next(e for e in events if e["type"] == "status_changed")
    assert ev["data"]["from"] == "applied"
    assert ev["data"]["to"] == "interviewing"


def test_tags_updated_payload_added_removed_sorted(client):
    res = client.post(
        "/jobs/",
        json={
            "company_name": "Acme",
            "job_title": "Engineer",
            "location": None,
            "job_url": None,
            "tags": ["python", "remote"],
        },
    )
    assert res.status_code == 200
    job = res.json()

    # Replace tags: remove "remote", add "onsite" (also test normalization + de-dupe)
    res2 = client.patch(f"/jobs/{job['id']}", json={"tags": ["Python", "onsite", "python"]})
    assert res2.status_code == 200

    events = _activity_items(client, job["id"])
    ev = next(e for e in events if e["type"] == "tags_updated")

    assert ev["data"]["added"] == ["onsite"]
    assert ev["data"]["removed"] == ["remote"]


def test_activity_metrics_endpoint(client):
    job = client.post(
        "/jobs/",
        json={"company_name": "TestCo", "job_title": "Engineer"},
    ).json()

    client.post(f"/jobs/{job['id']}/notes", json={"body": "Ping hiring manager"})

    metrics = client.get("/jobs/metrics/activity?range_days=7")
    assert metrics.status_code == 200
    data = metrics.json()
    assert data["total_events"] >= 1


