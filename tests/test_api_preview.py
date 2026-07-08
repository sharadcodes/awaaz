from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from awaaz.domain.exceptions import TtsRequestError


def test_preview_voice_success(client: TestClient) -> None:
    async def mock_synthesize(self: object, text: str, target: Path, *, speed: float = 1.0) -> None:
        import wave

        with wave.open(str(target), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24_000)
            output.writeframes(b"\x00\x00" * 2_400)

    with patch("awaaz.adapters.openai_tts.OpenAiTtsAdapter.synthesize", new=mock_synthesize):
        response = client.post(
            "/api/v1/backends/kokoro/preview",
            json={"voice": "af_bella", "model": "kokoro", "speed": 1.0, "text": "Hello world"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        assert len(response.content) > 0


def test_preview_voice_unknown_backend(client: TestClient) -> None:
    response = client.post(
        "/api/v1/backends/unknown/preview",
        json={"voice": "af_bella", "model": "kokoro", "speed": 1.0, "text": "Hello world"},
    )
    assert response.status_code == 404


def test_preview_voice_too_long(client: TestClient) -> None:
    response = client.post(
        "/api/v1/backends/kokoro/preview",
        json={"voice": "af_bella", "model": "kokoro", "speed": 1.0, "text": "a" * 5000},
    )
    assert response.status_code == 422


def test_preview_voice_adapter_error(client: TestClient) -> None:
    async def mock_fail(self: object, text: str, target: Path, *, speed: float = 1.0) -> None:
        raise TtsRequestError("TTS backend offline", retryable=False)

    with patch("awaaz.adapters.openai_tts.OpenAiTtsAdapter.synthesize", new=mock_fail):
        response = client.post(
            "/api/v1/backends/kokoro/preview",
            json={"voice": "af_bella", "model": "kokoro", "speed": 1.0, "text": "Hello world"},
        )
        assert response.status_code == 502
