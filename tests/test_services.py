from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from awaaz.adapters.registry import AdapterFactory
from awaaz.config import Settings
from awaaz.domain.exceptions import DocumentError, JobError
from awaaz.models import Chunk, Document, Job
from awaaz.schemas import JobCreate
from awaaz.services.documents import update_document_text
from awaaz.services.jobs import create_job, serialize_job, set_job_state
from awaaz.services.queue import QueueWorker


@pytest.mark.asyncio
async def test_job_creation_persists_ordered_chunks_and_progress(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    async with sessions() as session:
        document = Document(title="Book", text="First.\n\nSecond.")
        session.add(document)
        await session.commit()

        job = await create_job(session, document, JobCreate(character_limit=100), settings)
        chunks = (
            await session.scalars(select(Chunk).where(Chunk.job_id == job.id).order_by(Chunk.position))
        ).all()
        response = await serialize_job(session, job)

    assert [chunk.text for chunk in chunks] == ["First.", "Second."]
    assert response.status == "queued"
    assert response.progress.total == 2
    assert response.progress.percent == 0


@pytest.mark.asyncio
async def test_edit_rejects_active_job(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as session:
        document = Document(title="Book", text="Old")
        session.add(document)
        await session.flush()
        session.add(
            Job(
                document_id=document.id,
                document_revision=1,
                backend="kokoro",
                model="kokoro",
                voice="af_bella",
                chunking_mode="whole",
                character_limit=10,
            )
        )
        await session.commit()

        with pytest.raises(DocumentError, match="cancel active"):
            await update_document_text(session, document.id, "New", 1)


@pytest.mark.asyncio
async def test_resume_returns_failed_chunks_to_queue(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as session:
        document = Document(title="Book", text="Text")
        session.add(document)
        await session.flush()
        job = Job(
            document_id=document.id,
            document_revision=1,
            status="failed",
            backend="kokoro",
            model="kokoro",
            voice="af_bella",
            chunking_mode="whole",
            character_limit=10,
        )
        session.add(job)
        await session.flush()
        chunk = Chunk(job_id=job.id, position=0, text="Text", status="failed", error="busy")
        session.add(chunk)
        await session.commit()

        resumed = await set_job_state(session, job.id, "resume")
        await session.refresh(chunk)

    assert resumed.status == "queued"
    assert chunk.status == "pending"
    assert chunk.error is None


@pytest.mark.asyncio
async def test_worker_recovery_requeues_abandoned_chunk(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    async with sessions() as session:
        document = Document(title="Book", text="Text")
        session.add(document)
        await session.flush()
        job = Job(
            document_id=document.id,
            document_revision=1,
            backend="kokoro",
            model="kokoro",
            voice="af_bella",
            chunking_mode="whole",
            character_limit=10,
        )
        session.add(job)
        await session.flush()
        chunk = Chunk(job_id=job.id, position=0, text="Text", status="processing")
        session.add(chunk)
        await session.commit()
        chunk_id = chunk.id

    worker = QueueWorker(sessions, settings, AdapterFactory(settings))
    await worker.recover_abandoned()

    async with sessions() as session:
        recovered = await session.get(Chunk, chunk_id)
        assert recovered is not None
        assert recovered.status == "pending"


@pytest.mark.asyncio
async def test_worker_processes_jobs_in_round_robin_order(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    """With one worker, chunks from multiple active jobs should be interleaved."""
    from unittest.mock import AsyncMock, patch

    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    async with sessions() as session:
        for title in ("Book A", "Book B"):
            document = Document(title=title, text="One. Two. Three.")
            session.add(document)
            await session.flush()
            job = Job(
                document_id=document.id,
                document_revision=1,
                status="queued",
                backend="kokoro",
                model="kokoro",
                voice="af_bella",
                chunking_mode="sentence",
                character_limit=10,
            )
            session.add(job)
            await session.flush()
            for position, text in enumerate(["One.", "Two.", "Three."]):
                session.add(Chunk(job_id=job.id, position=position, text=text))
        await session.commit()

    worker = QueueWorker(sessions, settings, AdapterFactory(settings))
    await worker.recover_abandoned()

    processed_order: list[str] = []
    with patch("awaaz.db.session_factory", sessions), patch.object(
        worker._adapters, "create", return_value=AsyncMock()
    ) as mock_create:
        mock_adapter = AsyncMock()
        mock_adapter.synthesize.return_value = None
        mock_create.return_value = mock_adapter
        for _ in range(6):
            await worker.process_once()
            async with sessions() as session:
                completed = (
                    await session.scalars(
                        select(Chunk)
                        .where(Chunk.status == "completed")
                        .order_by(Chunk.updated_at)
                    )
                ).all()
                if len(completed) > len(processed_order):
                    latest = completed[-1]
                    job = await session.get(Job, latest.job_id)
                    document = await session.get(Document, job.document_id) if job else None
                    processed_order.append(document.title if document else str(latest.job_id))

    # Round-robin should interleave chunks from both jobs. The first job
    # depends on UUID ordering (created_at is identical for same-flush jobs),
    # so only assert that the two books alternate — not which goes first.
    assert len(processed_order) == 6
    assert len(set(processed_order)) == 2
    for i in range(1, len(processed_order)):
        assert processed_order[i] != processed_order[i - 1], "jobs should alternate"


def test_adapter_factory_rejects_unknown_backend() -> None:
    with pytest.raises(JobError, match="unknown backend"):
        AdapterFactory(Settings()).create("missing", "model", "voice")

