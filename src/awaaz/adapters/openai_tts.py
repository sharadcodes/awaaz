from pathlib import Path

import aiofiles
import httpx

from awaaz.config import BackendSettings
from awaaz.domain.exceptions import TtsRequestError


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
            raise TtsRequestError("TTS server returned empty audio", retryable=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        async with aiofiles.open(temporary, "wb") as output:
            await output.write(response.content)
        temporary.replace(target)

