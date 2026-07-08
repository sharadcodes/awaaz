from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient


def test_list_backend_voices_kokoro_dict(client: TestClient) -> None:
    mock_response_data = {
        "voices": [
            {"id": "af_alloy", "name": "af_alloy"},
            {"id": "af_bella", "name": "af_bella"},
            {"id": "invalid_voice"},  # missing name should still fallback to id
        ]
    }

    mock_response = httpx.Response(status_code=200, json=mock_response_data)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        response = client.get("/api/v1/backends/kokoro/voices")

        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "kokoro"
        assert data["voices"] == ["af_alloy", "af_bella", "invalid_voice"]


def test_list_backend_voices_kokoro_list(client: TestClient) -> None:
    mock_response_data = {"voices": ["af_alloy", "af_bella"]}

    mock_response = httpx.Response(status_code=200, json=mock_response_data)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        response = client.get("/api/v1/backends/kokoro/voices")

        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "kokoro"
        assert data["voices"] == ["af_alloy", "af_bella"]


def test_list_backend_voices_supertonic(client: TestClient) -> None:
    mock_response_data = {"styles": [{"name": "style_1"}, {"name": "style_2"}]}

    mock_response = httpx.Response(status_code=200, json=mock_response_data)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        response = client.get("/api/v1/backends/supertonic/voices")

        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "supertonic"
        assert data["voices"] == ["style_1", "style_2"]


def test_list_backend_voices_unknown(client: TestClient) -> None:
    response = client.get("/api/v1/backends/unknown/voices")
    assert response.status_code == 404
