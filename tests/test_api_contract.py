from awaaz.api import list_backends
from awaaz.config import Settings
from awaaz.main import app


def test_required_routes_are_in_openapi_schema() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/documents/upload" in paths
    assert "/api/v1/documents/{document_id}/text" in paths
    assert "/api/v1/documents/{document_id}/jobs" in paths
    assert "/api/v1/jobs/{job_id}/events" in paths
    assert "/api/v1/jobs/{job_id}/download" in paths
    assert "/v1/audio/speech" in paths


async def test_backend_discovery_contains_env_configured_values() -> None:
    settings = Settings()

    backends = await list_backends(settings)

    assert backends[0]["name"] == "supertonic"
    assert backends[0]["base_url"] == settings.supertonic.base_url
    assert backends[1]["name"] == "kokoro"

