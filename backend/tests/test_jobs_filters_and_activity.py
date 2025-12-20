from __future__ import annotations


def _create_job(client, company: str, title: str, location: str | None, status: str | None, tags: list[str] | None):
    payload = {"company_name": company, "job_title": title, "location": location, "job_url": None, "tags": tags or []}
    res = client.post("/jobs/", json=payload)
    assert res.status_code == 200
    job = res.json()
    if status:
        res2 = client.patch(f"/jobs/{job['id']}", json={"status": status})
        assert res2.status_code == 200
        job = res2.json()
    return job


def test_list_jobs_filters_q_status_tag_tag_q(client):
    j1 = _create_job(client, "Acme", "Engineer", "Remote", "applied", ["python", "backend"])
    j2 = _create_job(client, "Globex", "Designer", "NYC", "rejected", ["ui", "figma"])

    # q matches company/title/location (company)
    res = client.get("/jobs/", params={"q": "acm"})
    assert res.status_code == 200
    ids = [j["id"] for j in res.json()]
    assert j1["id"] in ids
    assert j2["id"] not in ids

    # status any-of
    res2 = client.get("/jobs/", params=[("status", "rejected")])
    ids2 = [j["id"] for j in res2.json()]
    assert j2["id"] in ids2
    assert j1["id"] not in ids2

    # tag exact any-of
    res3 = client.get("/jobs/", params=[("tag", "backend")])
    ids3 = [j["id"] for j in res3.json()]
    assert j1["id"] in ids3
    assert j2["id"] not in ids3

    # tag_q substring match
    res4 = client.get("/jobs/", params={"tag_q": "fig"})
    ids4 = [j["id"] for j in res4.json()]
    assert j2["id"] in ids4
    assert j1["id"] not in ids4


def test_job_status_and_tags_updates_log_activity(client):
    job = _create_job(client, "Acme", "Engineer", None, None, ["python"])

    res = client.patch(f"/jobs/{job['id']}", json={"status": "interviewing"})
    assert res.status_code == 200

    res2 = client.patch(f"/jobs/{job['id']}", json={"tags": ["python", "remote"]})
    assert res2.status_code == 200

    res3 = client.get(f"/jobs/{job['id']}/activity")
    assert res3.status_code == 200
    types = [ev["type"] for ev in res3.json()]
    assert "status_changed" in types
    assert "tags_updated" in types


