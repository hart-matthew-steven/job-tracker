def test_saved_views_crud(client):
    # Create
    res = client.post("/saved-views/", json={"name": "My View", "data": {"q": "acme"}})
    assert res.status_code == 201
    sv = res.json()
    assert sv["name"] == "My View"
    assert sv["data"]["q"] == "acme"

    # List
    res = client.get("/saved-views/")
    assert res.status_code == 200
    lst = res.json()
    assert any(v["id"] == sv["id"] for v in lst)

    # Duplicate name -> 409
    res = client.post("/saved-views/", json={"name": "My View", "data": {"q": "x"}})
    assert res.status_code == 409

    # Patch
    res = client.patch(f"/saved-views/{sv['id']}", json={"data": {"q": "updated"}})
    assert res.status_code == 200
    assert res.json()["data"]["q"] == "updated"

    # Delete
    res = client.delete(f"/saved-views/{sv['id']}")
    assert res.status_code == 200
    assert res.json()["message"] == "Saved view deleted"


def test_saved_views_rename_conflict_is_409(client):
    res1 = client.post("/saved-views/", json={"name": "View A", "data": {"q": "a"}})
    assert res1.status_code == 201
    a = res1.json()

    res2 = client.post("/saved-views/", json={"name": "View B", "data": {"q": "b"}})
    assert res2.status_code == 201
    b = res2.json()

    res3 = client.patch(f"/saved-views/{b['id']}", json={"name": a["name"]})
    assert res3.status_code == 409


