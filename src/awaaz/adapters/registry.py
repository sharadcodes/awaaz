from awaaz.adapters.openai_tts import OpenAiTtsAdapter
from awaaz.config import Settings
from awaaz.domain.exceptions import JobError


class AdapterFactory:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, backend: str, model: str, voice: str) -> OpenAiTtsAdapter:
        configured = {
            "supertonic": self._settings.supertonic,
            "kokoro": self._settings.kokoro,
            "custom": self._settings.custom,
        }.get(backend)
        if configured is None:
            raise JobError(f"unknown backend: {backend}")
        return OpenAiTtsAdapter(configured, model=model, voice=voice)
