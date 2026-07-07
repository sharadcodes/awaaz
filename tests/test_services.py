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


def test_adapter_factory_rejects_unknown_backend() -> None:
    with pytest.raises(JobError, match="unknown backend"):
        AdapterFactory(Settings()).create("missing", "model", "voice")

