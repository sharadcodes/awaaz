from pathlib import Path

import httpx
import pytest

from awaaz.adapters.openai_tts import OpenAiTtsAdapter
from awaaz.config import BackendSettings
from awaaz.domain.exceptions import TtsRequestError


@pytest.mark.asyncio
async def test_adapter_sends_openai_compatible_payload(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://tts.test/v1/audio/speech"
        assert request.headers["authorization"] == "Bearer secret"
        assert request.read() == (
            b'{"model":"voice-model","input":"Hello","voice":"narrator",'
            b'"response_format":"wav","speed":1.1}'
        )
        return httpx.Response(200, content=b"RIFFaudio", headers={"content-type": "audio/wav"})

    settings = BackendSettings(
        base_url="http://tts.test/v1",
        api_key="secret",
        model="voice-model",
        voice="narrator",
    )
    adapter = OpenAiTtsAdapter(settings, transport=httpx.MockTransport(handler))
    target = tmp_path / "chunk.wav"

    await adapter.synthesize("Hello", target, speed=1.1)

    assert target.read_bytes() == b"RIFFaudio"


@pytest.mark.asyncio
async def test_adapter_raises_custom_error_on_server_failure(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(503, text="busy"))
    adapter = OpenAiTtsAdapter(BackendSettings(), transport=transport)

    with pytest.raises(TtsRequestError, match="503") as error:
        await adapter.synthesize("Hello", tmp_path / "chunk.wav")

    assert error.value.retryable is True


@pytest.mark.asyncio
async def test_adapter_writes_silent_wav_for_empty_response(tmp_path: Path) -> None:
    """Non-speakable text (e.g. '***') gets a silent WAV placeholder, not an error."""
    import wave

    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b""))
    adapter = OpenAiTtsAdapter(BackendSettings(), transport=transport)
    target = tmp_path / "chunk.wav"

    await adapter.synthesize("***", target)

    assert target.exists()
    with wave.open(str(target), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 24000
        assert wav.getnframes() > 0

