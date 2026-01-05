from datetime import datetime, timedelta, timezone


def _create_job(client):
    res = client.post(
        "/jobs/",
        json={"company_name": "Acme", "job_title": "Engineer", "location": "Remote", "job_url": None, "tags": []},
    )
    assert res.status_code == 200
    return res.json()


def test_notes_create_delete_logs_activity(client):
    job = _create_job(client)

    res = client.post(f"/jobs/{job['id']}/notes", json={"body": "hello"})
    assert res.status_code == 200
    note = res.json()
    assert note["body"] == "hello"

    res2 = client.get(f"/jobs/{job['id']}/notes")
    assert res2.status_code == 200
    assert len(res2.json()) == 1

    res3 = client.get(f"/jobs/{job['id']}/activity")
    assert res3.status_code == 200
    payload = res3.json()
    assert any(ev["type"] == "note_added" for ev in payload.get("items") or [])

    res4 = client.delete(f"/jobs/{job['id']}/notes/{note['id']}")
    assert res4.status_code == 200
    assert res4.json()["deleted"] is True

    res5 = client.get(f"/jobs/{job['id']}/activity")
    payload5 = res5.json()
    assert any(ev["type"] == "note_deleted" for ev in payload5.get("items") or [])


def test_interviews_crud_logs_activity(client):
    job = _create_job(client)
    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    res = client.post(
        f"/jobs/{job['id']}/interviews",
        json={"scheduled_at": when, "stage": "Recruiter", "kind": "Phone", "status": "scheduled"},
    )
    assert res.status_code == 200
    iv = res.json()
    assert iv["status"] == "scheduled"

    res2 = client.patch(
        f"/jobs/{job['id']}/interviews/{iv['id']}",
        json={"status": "completed"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "completed"

    res3 = client.delete(f"/jobs/{job['id']}/interviews/{iv['id']}")
    assert res3.status_code == 200

    res4 = client.get(f"/jobs/{job['id']}/activity")
    payload = res4.json()
    types = [ev["type"] for ev in payload.get("items") or []]
    assert "interview_added" in types
    assert "interview_updated" in types
    assert "interview_deleted" in types


