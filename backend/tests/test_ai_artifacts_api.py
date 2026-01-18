from __future__ import annotations

def test_create_text_artifact_and_list(client, users, monkeypatch):
    user, _ = users
    convo = client.post("/ai/conversations", json={"title": "Artifacts Chat"})
    conversation_id = convo.json()["id"]

    calls: list[tuple] = []

    def fake_enqueue(task, *args, **kwargs):
        calls.append((task.name, args, kwargs))

    monkeypatch.setattr("app.services.artifacts.enqueue", fake_enqueue)
    resp = client.post(
        "/ai/artifacts/text",
        json={
            "conversation_id": conversation_id,
            "artifact_type": "resume",
            "content": "John Doe - Software Engineer",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ready"

    list_resp = client.get(f"/ai/artifacts/conversations/{conversation_id}")
    assert list_resp.status_code == 200
    artifacts = list_resp.json()["artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["artifact_type"] == "resume"
    assert artifacts[0]["status"] == "ready"
    if artifacts[0]["view_url"]:
        assert artifacts[0]["view_url"].startswith("https://example.invalid/view/")


def test_upload_flow_queues_processing(client, monkeypatch):
    convo = client.post("/ai/conversations", json={"title": "Resume Upload"})
    conversation_id = convo.json()["id"]

    created: dict = {}

    def fake_enqueue(task, *args, **kwargs):
        created["queued"] = {"task": task.name, "args": args}

    monkeypatch.setattr("app.services.artifacts.enqueue", fake_enqueue)

    upload = client.post(
        "/ai/artifacts/upload-url",
        json={
            "conversation_id": conversation_id,
            "artifact_type": "resume",
            "filename": "resume.docx",
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
    )
    assert upload.status_code == 201
    artifact_id = upload.json()["artifact_id"]
    assert "upload_url" in upload.json()

    finalize = client.post(f"/ai/artifacts/{artifact_id}/complete-upload")
    assert finalize.status_code == 200
    assert finalize.json()["status"] == "pending"
    assert created["queued"]["args"][0] == artifact_id


def test_url_artifact_queues_scrape(client, monkeypatch):
    convo = client.post("/ai/conversations", json={"title": "JD Scrape"})
    conversation_id = convo.json()["id"]
    queued = {}

    def fake_enqueue(task, *args, **kwargs):
        queued["task"] = task.name
        queued["args"] = args

    monkeypatch.setattr("app.services.artifacts.enqueue", fake_enqueue)
    resp = client.post(
        "/ai/artifacts/url",
        json={
            "conversation_id": conversation_id,
            "artifact_type": "job_description",
            "url": "https://example.com/job",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"
    assert queued["task"] == "artifacts.scrape_job_description"
