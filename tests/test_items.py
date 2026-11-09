import pytest

URL = "/api/v1/items"


def test_list_starts_empty(client):
    resp = client.get(URL)
    assert resp.status_code == 200
    assert resp.get_json() == {"count": 0, "items": []}


def test_create_item_returns_201_and_location(client):
    resp = client.post(URL, json={"sku": "ABC-1", "name": "Alpha", "quantity": 5})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["sku"] == "ABC-1" and body["quantity"] == 5
    assert resp.headers["Location"] == f"{URL}/{body['id']}"


def test_create_defaults_quantity_to_zero(client):
    resp = client.post(URL, json={"sku": "ZERO-1", "name": "Zero stock"})
    assert resp.status_code == 201
    assert resp.get_json()["quantity"] == 0


@pytest.mark.parametrize(
    "payload, fragment",
    [
        ({"name": "No sku"}, "sku must be"),
        ({"sku": "X-1"}, "name must be"),
        ({"sku": "X-1", "name": "Negative", "quantity": -1}, "quantity must be"),
        ({"sku": "X-1", "name": "Boolean", "quantity": True}, "quantity must be"),
        ({"sku": "X-1", "name": "Extra", "colour": "red"}, "unknown fields: colour"),
    ],
)
def test_create_rejects_invalid_payload(client, payload, fragment):
    resp = client.post(URL, json=payload)
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "Bad Request"
    assert fragment in body["message"]


def test_create_rejects_non_json(client):
    resp = client.post(URL, data="sku=abc", content_type="application/x-www-form-urlencoded")
    assert resp.status_code == 400
    assert "JSON object" in resp.get_json()["message"]


def test_duplicate_sku_returns_409(client, make_item):
    make_item(sku="DUP-1")
    resp = client.post(URL, json={"sku": "DUP-1", "name": "Again"})
    assert resp.status_code == 409
    body = resp.get_json()
    assert body["error"] == "Conflict"
    assert "DUP-1" in body["message"]
    assert client.get(URL).get_json()["count"] == 1


def test_get_missing_item_returns_json_404(client):
    resp = client.get(f"{URL}/999")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Not Found", "message": "Item 999 not found", "status": 404}


def test_patch_updates_only_given_fields(client, make_item):
    item = make_item(quantity=10)
    resp = client.patch(f"{URL}/{item['id']}", json={"quantity": 42})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["quantity"] == 42
    assert body["sku"] == item["sku"] and body["name"] == item["name"]


def test_patch_missing_item_returns_404(client):
    assert client.patch(f"{URL}/999", json={"quantity": 1}).status_code == 404


def test_patch_rejects_invalid_quantity(client, make_item):
    item = make_item()
    resp = client.patch(f"{URL}/{item['id']}", json={"quantity": -5})
    assert resp.status_code == 400


def test_patch_rejects_empty_body(client, make_item):
    item = make_item()
    resp = client.patch(f"{URL}/{item['id']}", json={})
    assert resp.status_code == 400
    assert "at least one" in resp.get_json()["message"]


def test_delete_item(client, make_item):
    item = make_item()
    resp = client.delete(f"{URL}/{item['id']}")
    assert resp.status_code == 204
    assert resp.data == b""
    assert client.get(f"{URL}/{item['id']}").status_code == 404


def test_filters(client, make_item):
    make_item(sku="A-1", name="Hex bolt", quantity=5)
    make_item(sku="A-2", name="Hex nut", quantity=50)
    make_item(sku="A-3", name="Washer", quantity=500)
    resp = client.get(f"{URL}?min_quantity=40")
    assert [i["sku"] for i in resp.get_json()["items"]] == ["A-2", "A-3"]
    assert client.get(f"{URL}?q=hex").get_json()["count"] == 2


def test_method_not_allowed_is_json(client):
    resp = client.delete(URL)
    assert resp.status_code == 405
    assert resp.is_json
    assert "POST" in resp.headers["Allow"]
