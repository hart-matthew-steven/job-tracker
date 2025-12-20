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


