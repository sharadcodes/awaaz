from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from awaaz.adapters.registry import AdapterFactory
from awaaz.config import Settings
from awaaz.models import Chunk, Document, Job
from awaaz.services.queue import QueueWorker


async def _completed_job(sessions: async_sessionmaker[AsyncSession]) -> str:
    async with sessions() as session:
        document = Document(title="Book", text="Text")
        session.add(document)
        await session.flush()
        job = Job(
            document_id=document.id,
            document_revision=1,
            status="running",
            backend="kokoro",
            model="kokoro",
            voice="af_bella",
            chunking_mode="whole",
            character_limit=10,
        )
        session.add(job)
        await session.flush()
        session.add(
            Chunk(
                job_id=job.id,
                position=0,
                text="Text",
                status="completed",
                audio_path="/missing/checkpoint.wav",
            )
        )
        await session.commit()
        return job.id


@pytest.mark.asyncio
async def test_ready_job_assembly_failure_is_persisted_not_raised(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    job_id = await _completed_job(sessions)
    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    worker = QueueWorker(sessions, settings, AdapterFactory(settings))

    assert await worker.process_once() is True

    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        assert "must exist" in (job.error or "")


@pytest.mark.asyncio
async def test_startup_recovers_interrupted_assembly(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    job_id = await _completed_job(sessions)
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        job.status = "assembling"
        await session.commit()
    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    worker = QueueWorker(sessions, settings, AdapterFactory(settings))

    await worker.recover_abandoned()

    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "running"
