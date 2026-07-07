from fastapi.testclient import TestClient


def test_document_collection_names_returned(client: TestClient) -> None:
    doc_resp = client.post("/api/v1/documents", json={"title": "Doc", "text": "Hello"})
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    coll_resp = client.post("/api/v1/collections", json={"name": "c1"})
    assert coll_resp.status_code == 201
    coll_id = coll_resp.json()["id"]

    put_resp = client.put(
        f"/api/v1/collections/{coll_id}",
        json={"name": "c1", "document_ids": [doc_id]},
    )
    assert put_resp.status_code == 200

    list_resp = client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    assert doc is not None, "doc not found in list"
    print("collection_names:", doc["collection_names"])
    assert "c1" in doc["collection_names"], f"expected c1 in {doc['collection_names']}"
