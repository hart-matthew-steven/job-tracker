from app.models.user import User


def test_update_ui_preferences_success(client, db_session, users):
    resp = client.patch(
        "/users/me/ui-preferences",
        json={"preferences": {"job_details_notes_collapsed": True, "job_details_documents_collapsed": False}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ui_preferences"]["job_details_notes_collapsed"] is True
    assert body["ui_preferences"]["job_details_documents_collapsed"] is False

    user_a, _ = users
    refreshed = db_session.query(User).filter(User.id == user_a.id).first()
    assert refreshed.ui_preferences["job_details_notes_collapsed"] is True
    assert refreshed.ui_preferences["job_details_documents_collapsed"] is False


def test_update_ui_preferences_rejects_unknown_key(client):
    resp = client.patch(
        "/users/me/ui-preferences",
        json={"preferences": {"unknown_key": True}},
    )
    assert resp.status_code == 400
    assert "Unknown preference key" in resp.json()["detail"]


