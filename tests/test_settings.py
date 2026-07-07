from awaaz.config import Settings


def test_documented_engine_defaults_use_compose_service_names() -> None:
    settings = Settings()

    assert settings.supertonic.base_url == "http://supertonic:7788/v1"
    assert settings.supertonic.model == "supertonic-3"
    assert settings.supertonic.voice == "M1"
    assert settings.kokoro.base_url == "http://kokoro:8880/v1"
    assert settings.kokoro.model == "kokoro"
    assert settings.kokoro.voice == "af_bella"
    assert settings.worker_concurrency == 1

