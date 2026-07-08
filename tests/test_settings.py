import os

from awaaz.config import Settings


def test_documented_engine_defaults_use_compose_service_names(monkeypatch) -> None:
    # Isolate the test from local .env / AWAAZ_* overrides so it asserts
    # the documented defaults rather than whatever the developer configured.
    for key in list(os.environ.keys()):
        if key.startswith("AWAAZ_"):
            monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.supertonic.base_url == "http://supertonic:7788/v1"
    assert settings.supertonic.model == "supertonic-3"
    assert settings.supertonic.voice == "M1"
    assert settings.kokoro.base_url == "http://kokoro:8880/v1"
    assert settings.kokoro.model == "kokoro"
    assert settings.kokoro.voice == "af_bella"
    assert settings.worker_concurrency == 1
