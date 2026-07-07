import wave
from pathlib import Path

import aiofiles
import httpx

from awaaz.config import BackendSettings
from awaaz.domain.exceptions import TtsRequestError


def _write_silent_wav(target: Path, *, sample_rate: int = 24000, duration: float = 0.5) -> None:
    """Write a short silent mono 16-bit WAV file for non-speakable text (e.g. '***')."""
    n_frames = int(sample_rate * duration)
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * n_frames)


class OpenAiTtsAdapter:
    def __init__(
        self,
        settings: BackendSettings,
        *,
        model: str | None = None,
        voice: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._model = model or settings.model
        self._voice = voice or settings.voice
        self._transport = transport

    async def synthesize(self, text: str, target: Path, *, speed: float = 1.0) -> None:
        headers = {"Authorization": f"Bearer {self._settings.api_key}"}
        payload = {
            "model": self._model,
            "input": text,
            "voice": self._voice,
            "response_format": "wav",
            "speed": speed,
        }
        timeout = httpx.Timeout(self._settings.timeout_seconds)
        try:
            async with httpx.AsyncClient(
                headers=headers, timeout=timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self._settings.base_url.rstrip('/')}/audio/speech", json=payload
                )
        except httpx.RequestError as error:
            raise TtsRequestError(str(error), retryable=True) from error
        if response.status_code >= 400:
            retryable = response.status_code in {408, 429} or response.status_code >= 500
            raise TtsRequestError(
                f"TTS server returned {response.status_code}: {response.text[:500]}",
                retryable=retryable,
            )
        if not response.content:
            # Some TTS servers return 200 with an empty body for text that has
            # no speakable tokens (e.g. scene-break markers like '***'). Treat
            # this as a short silent pause instead of failing the whole job.
            _write_silent_wav(target)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        async with aiofiles.open(temporary, "wb") as output:
            await output.write(response.content)
        temporary.replace(target)
