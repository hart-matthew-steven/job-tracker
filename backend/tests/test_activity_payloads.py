from __future__ import annotations


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

    res3 = client.get(f"/jobs/{job['id']}/activity")
    assert res3.status_code == 200
    assert all(ev["type"] != "status_changed" for ev in res3.json())

    # Changing status should log with from/to and normalized "to".
    res4 = client.patch(f"/jobs/{job['id']}", json={"status": "  Interviewing  "})
    assert res4.status_code == 200
    assert res4.json()["status"] == "interviewing"

    res5 = client.get(f"/jobs/{job['id']}/activity")
    assert res5.status_code == 200
    events = res5.json()
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

    res3 = client.get(f"/jobs/{job['id']}/activity")
    assert res3.status_code == 200
    events = res3.json()
    ev = next(e for e in events if e["type"] == "tags_updated")

    assert ev["data"]["added"] == ["onsite"]
    assert ev["data"]["removed"] == ["remote"]


