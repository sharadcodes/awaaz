from fastapi.testclient import TestClient


def test_put_collection_adds_documents(client: TestClient) -> None:
    create_resp = client.post("/api/v1/collections", json={"name": "c1"})
    assert create_resp.status_code == 201
    collection_id = create_resp.json()["id"]

    doc_resp = client.post("/api/v1/documents", json={"title": "Doc", "text": "Hello world"})
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    put_resp = client.put(
        f"/api/v1/collections/{collection_id}",
        json={"name": "c1", "document_ids": [doc_id]},
    )
    assert put_resp.status_code == 200, put_resp.text
    data = put_resp.json()
    assert data["document_count"] == 1
    assert data["name"] == "c1"


def test_put_collection_rejects_duplicate_name(client: TestClient) -> None:
    first = client.post("/api/v1/collections", json={"name": "c1"})
    assert first.status_code == 201
    second_id = client.post("/api/v1/collections", json={"name": "c2"}).json()["id"]

    put_resp = client.put(
        f"/api/v1/collections/{second_id}",
        json={"name": "c1"},
    )
    assert put_resp.status_code == 400, put_resp.text
    assert "unique" in put_resp.json()["detail"].lower()
