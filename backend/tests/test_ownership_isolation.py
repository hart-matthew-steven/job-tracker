from __future__ import annotations


def _create_job(client):
    res = client.post(
        "/jobs/",
        json={"company_name": "Acme", "job_title": "Engineer", "location": None, "job_url": None, "tags": []},
    )
    assert res.status_code == 200
    return res.json()


def test_user_cannot_access_other_users_job_or_subresources(users, client_for):
    user_a, user_b = users

    with client_for(user_a) as c_a:
        job = _create_job(c_a)

        # Create note
        res_note = c_a.post(f"/jobs/{job['id']}/notes", json={"body": "hello"})
        assert res_note.status_code == 200
        note_id = res_note.json()["id"]

        # Create interview
        res_iv = c_a.post(
            f"/jobs/{job['id']}/interviews",
            json={"scheduled_at": "2030-01-01T10:00:00Z", "stage": "phone", "kind": "screen", "notes": None},
        )
        assert res_iv.status_code == 200
        interview_id = res_iv.json()["id"]

        # Create pending doc
        res_doc = c_a.post(
            f"/jobs/{job['id']}/documents/presign-upload",
            json={"doc_type": "resume", "filename": "resume.pdf", "content_type": "application/pdf", "size_bytes": 10},
        )
        assert res_doc.status_code == 200
        doc_id = res_doc.json()["document"]["id"]

        # Activity exists
        res_act = c_a.get(f"/jobs/{job['id']}/activity")
        assert res_act.status_code == 200
        assert isinstance(res_act.json(), list)

    # Now verify user_b cannot access any of it.
    with client_for(user_b) as c_b:
        # Jobs
        assert c_b.get(f"/jobs/{job['id']}").status_code == 404

        # Notes
        assert c_b.get(f"/jobs/{job['id']}/notes").status_code == 404
        assert c_b.delete(f"/jobs/{job['id']}/notes/{note_id}").status_code == 404

        # Interviews
        assert c_b.get(f"/jobs/{job['id']}/interviews").status_code == 404
        assert c_b.patch(f"/jobs/{job['id']}/interviews/{interview_id}", json={"status": "done"}).status_code == 404
        assert c_b.delete(f"/jobs/{job['id']}/interviews/{interview_id}").status_code == 404

        # Documents
        assert c_b.get(f"/jobs/{job['id']}/documents").status_code == 404
        assert c_b.post(
            f"/jobs/{job['id']}/documents/confirm-upload",
            json={"document_id": doc_id},
        ).status_code == 404
        assert c_b.get(f"/jobs/{job['id']}/documents/{doc_id}/presign-download").status_code == 404
        assert c_b.delete(f"/jobs/{job['id']}/documents/{doc_id}").status_code == 404

        # Activity
        assert c_b.get(f"/jobs/{job['id']}/activity").status_code == 404


def test_user_list_jobs_only_returns_their_jobs(users, client_for):
    user_a, user_b = users

    with client_for(user_a) as c_a:
        _create_job(c_a)
        _create_job(c_a)

    with client_for(user_b) as c_b:
        _create_job(c_b)

    with client_for(user_a) as c_a2:
        res = c_a2.get("/jobs/")
        assert res.status_code == 200
        assert len(res.json()) == 2

    with client_for(user_b) as c_b2:
        res = c_b2.get("/jobs/")
        assert res.status_code == 200
        assert len(res.json()) == 1


