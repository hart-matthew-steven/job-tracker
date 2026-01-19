from __future__ import annotations

from app.models.artifact import AIArtifact, ArtifactStatus as ModelArtifactStatus


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
    summary = artifacts[0]
    assert summary["artifact_type"] == "resume"
    assert summary["role"] == "resume"
    assert summary["status"] == "ready"
    assert summary["view_url"] is None
    assert "pinned_at" in summary


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


def test_artifact_history_endpoint(client, db_session):
    convo = client.post("/ai/conversations", json={"title": "History"}).json()
    conversation_id = convo["id"]

    first = client.post(
        "/ai/artifacts/text",
        json={
            "conversation_id": conversation_id,
            "artifact_type": "resume",
            "content": "Line one",
        },
    ).json()["artifact_id"]

    client.post(
        "/ai/artifacts/text",
        json={
            "conversation_id": conversation_id,
            "artifact_type": "resume",
            "content": "Line one\nLine two",
        },
    )

    resp = client.get(f"/ai/artifacts/conversations/{conversation_id}/history", params={"role": "resume"})
    assert resp.status_code == 200
    history = resp.json()["artifacts"]
    assert len(history) == 2
    assert history[0]["artifact_id"] != history[1]["artifact_id"]
    assert history[0]["version_number"] == 2
    assert history[1]["version_number"] == 1
    assert history[1]["artifact_id"] == first


def test_artifact_diff_endpoint(client):
    convo = client.post("/ai/conversations", json={"title": "Diff"}).json()
    conversation_id = convo["id"]
    first = client.post(
        "/ai/artifacts/text",
        json={
            "conversation_id": conversation_id,
            "artifact_type": "resume",
            "content": "Header\nSkill A",
        },
    ).json()["artifact_id"]
    second = client.post(
        "/ai/artifacts/text",
        json={
            "conversation_id": conversation_id,
            "artifact_type": "resume",
            "content": "Header\nSkill A\nSkill B",
        },
    ).json()["artifact_id"]

    resp = client.get(f"/ai/artifacts/{second}/diff")
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifact_id"] == second
    assert data["compare_to_id"] == first
    ops = {(line["op"], line["text"]) for line in data["diff"]}
    assert ("insert", "Skill B") in ops


def test_ready_artifact_includes_presigned_view(client, db_session, monkeypatch):
    convo = client.post("/ai/conversations", json={"title": "Resume Upload"})
    conversation_id = convo.json()["id"]

    def fake_enqueue(task, *args, **kwargs):
        return None

    monkeypatch.setattr("app.services.artifacts.enqueue", fake_enqueue)

    upload = client.post(
        "/ai/artifacts/upload-url",
        json={
            "conversation_id": conversation_id,
            "artifact_type": "resume",
            "filename": "resume.pdf",
            "content_type": "application/pdf",
        },
    )
    artifact_id = upload.json()["artifact_id"]

    artifact = db_session.get(AIArtifact, artifact_id)
    artifact.status = ModelArtifactStatus.ready
    artifact.s3_key = "users/1/artifacts/ready.pdf"
    db_session.commit()

    resp = client.get(f"/ai/artifacts/conversations/{conversation_id}")
    summary = resp.json()["artifacts"][0]
    assert summary["view_url"].startswith("https://example.invalid/view/")
