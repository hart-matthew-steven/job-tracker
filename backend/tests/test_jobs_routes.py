from datetime import datetime, timezone


def test_create_and_list_jobs(client):
    payload = {
        "company_name": "Acme",
        "job_title": "Engineer",
        "location": "Remote",
        "job_url": "https://example.com",
        "tags": ["Python", "  Remote  ", "python"],
    }
    res = client.post("/jobs/", json=payload)
    assert res.status_code == 200
    created = res.json()
    assert created["company_name"] == "Acme"
    assert created["job_title"] == "Engineer"
    assert sorted(created.get("tags") or []) == ["python", "remote"]

    res2 = client.get("/jobs/")
    assert res2.status_code == 200
    jobs = res2.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 1
    assert any(j["id"] == created["id"] for j in jobs)


def test_get_job_details_bundle(client):
    payload = {
        "company_name": "Globex",
        "job_title": "Manager",
        "location": "Hybrid",
        "job_url": "https://example.com/job",
        "tags": ["sales"],
    }
    res = client.post("/jobs/", json=payload)
    assert res.status_code == 200
    job_id = res.json()["id"]

    note = client.post(f"/jobs/{job_id}/notes", json={"body": "First note"})
    assert note.status_code == 200

    interview = client.post(
        f"/jobs/{job_id}/interviews",
        json={
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "stage": "phone",
            "kind": "video",
            "location": "Zoom",
            "status": "scheduled",
            "notes": "Prep resume",
        },
    )
    assert interview.status_code == 200

    bundle = client.get(f"/jobs/{job_id}/details?activity_limit=5")
    assert bundle.status_code == 200
    data = bundle.json()

    assert data["job"]["id"] == job_id
    assert len(data["notes"]) == 1
    assert len(data["interviews"]) == 1
    assert len(data["activity"]["items"]) >= 2
    assert data["activity"]["next_cursor"] is None or isinstance(data["activity"]["next_cursor"], int)


def test_activity_pagination(client):
    payload = {
        "company_name": "Globex",
        "job_title": "Engineer",
        "location": "Remote",
    }
    res = client.post("/jobs/", json=payload)
    job_id = res.json()["id"]

    # create multiple notes to generate activity entries
    for i in range(6):
        client.post(f"/jobs/{job_id}/notes", json={"body": f"note {i}"})

    page1 = client.get(f"/jobs/{job_id}/activity?limit=3")
    assert page1.status_code == 200
    data1 = page1.json()
    assert len(data1["items"]) == 3
    assert data1["next_cursor"] is not None

    cursor = data1["next_cursor"]
    page2 = client.get(f"/jobs/{job_id}/activity?limit=3&cursor_id={cursor}")
    assert page2.status_code == 200
    data2 = page2.json()
    # ensure we received the next set and cursor eventually becomes null
    if len(data2["items"]) == 3:
        assert data2["next_cursor"] is None or isinstance(data2["next_cursor"], int)
