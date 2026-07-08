from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from awaaz.config import Settings


def test_document_upload_and_delete_cleanup(client: TestClient) -> None:
    settings = Settings()

    # Pre-create dirs
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.audio_dir.mkdir(parents=True, exist_ok=True)

    async def mock_extract_text(source: Path) -> str:
        return "This is my book text."

    async def mock_extract_metadata(source: Path) -> dict:
        return {"title": "Test Title", "authors": ["John Doe"]}

    async def mock_extract_cover(source: Path, target: Path) -> bool:
        target.write_bytes(b"dummy image data")
        return True

    # 1. Upload Document (EPUB)
    with (
        patch("awaaz.api.extract_text", new=mock_extract_text),
        patch("awaaz.api.extract_metadata", new=mock_extract_metadata),
        patch("awaaz.api.extract_cover", new=mock_extract_cover),
    ):
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test_book.epub", b"epub content bytes")},
        )
        assert response.status_code == 201
        doc_data = response.json()
        doc_id = doc_data["id"]
        cover_path = doc_data["cover_path"]
        assert cover_path is not None

        # Verify temporary files are deleted, cover image exists
        assert Path(cover_path).is_file()
        remaining_files = list(settings.uploads_dir.iterdir())
        assert len(remaining_files) == 1
        assert remaining_files[0] == Path(cover_path)

    # 2. Create a Job for the document
    response = client.post(
        f"/api/v1/documents/{doc_id}/jobs",
        json={
            "backend": "kokoro",
            "model": "kokoro",
            "voice": "af_bella",
            "speed": 1.0,
            "chunking_mode": "paragraph",
            "character_limit": 1000,
        },
    )
    assert response.status_code == 201
    job_data = response.json()
    job_id = job_data["id"]

    # 3. Simulate generated audio files on disk
    job_audio_dir = settings.audio_dir / job_id
    job_audio_dir.mkdir(parents=True, exist_ok=True)
    (job_audio_dir / "audiobook.mp3").write_bytes(b"mp3 data")
    chunks_dir = job_audio_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    (chunks_dir / "00000000.wav").write_bytes(b"wav chunk data")

    assert job_audio_dir.is_dir()
    assert (job_audio_dir / "audiobook.mp3").is_file()

    # 4. Cancel the Job (so the document can be deleted)
    response = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    # 5. Delete the Document
    response = client.delete(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 204

    # 5. Verify cover image is deleted
    assert not Path(cover_path).exists()

    # 6. Verify job audio directory is deleted
    assert not job_audio_dir.exists()
