def test_update_ui_preferences_success(client, db_session, users):
    resp = client.patch(
        "/users/me/ui-preferences",
        json={"preferences": {"job_details_notes_collapsed": True, "job_details_documents_collapsed": False}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ui_preferences"]["job_details_notes_collapsed"] is True
    assert body["ui_preferences"]["job_details_documents_collapsed"] is False

    resp_me = client.get("/users/me")
    assert resp_me.status_code == 200
    me = resp_me.json()
    assert me["ui_preferences"]["job_details_notes_collapsed"] is True
    assert me["ui_preferences"]["job_details_documents_collapsed"] is False


def test_update_ui_preferences_rejects_unknown_key(client):
    resp = client.patch(
        "/users/me/ui-preferences",
        json={"preferences": {"unknown_key": True}},
    )
    assert resp.status_code == 400
    body = resp.json()
    detail_msg = body.get("message") or body.get("detail") or ""
    assert "Unknown preference key" in detail_msg


