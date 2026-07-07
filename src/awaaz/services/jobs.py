from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from awaaz.config import Settings
from awaaz.domain.chunking import chunk_text
from awaaz.domain.exceptions import JobError
from awaaz.domain.progress import calculate_progress
from awaaz.models import Chunk, Document, Job, utc_now
from awaaz.schemas import JobCreate, JobRead, ProgressRead


def _backend_defaults(settings: Settings, name: str) -> tuple[str, str, int]:
    backend = {
        "supertonic": settings.supertonic,
        "kokoro": settings.kokoro,
        "custom": settings.custom,
    }.get(name)
    if backend is None:
        raise JobError(f"unknown backend: {name}")
    return backend.model, backend.voice, backend.max_characters


async def create_job(
    session: AsyncSession, document: Document, request: JobCreate, settings: Settings
) -> Job:
    default_model, default_voice, maximum = _backend_defaults(settings, request.backend)
    if request.character_limit > maximum:
        raise JobError(f"character limit exceeds backend maximum of {maximum}")
    texts = chunk_text(document.text, request.chunking_mode, request.character_limit)
    job = Job(
        document_id=document.id,
        document_revision=document.revision,
        backend=request.backend,
        model=request.model or default_model,
        voice=request.voice or default_voice,
        speed=request.speed,
        chunking_mode=request.chunking_mode.value,
        character_limit=request.character_limit,
    )
    session.add(job)
    await session.flush()
    chunks = []
    for position, text in enumerate(texts):
        chunk = Chunk(job_id=job.id, position=position, text=text)
        chunks.append(chunk)
        session.add(chunk)
    await session.commit()
    await session.refresh(job)

    # Chunks are persisted as pending; the QueueWorker will poll and process
    # them in round-robin order across active jobs.
    return job


async def get_job(session: AsyncSession, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise JobError("job not found")
    return job


async def serialize_job(session: AsyncSession, job: Job) -> JobRead:
    rows = (
        await session.execute(
            select(Chunk.status, func.count(Chunk.id))
            .where(Chunk.job_id == job.id)
            .group_by(Chunk.status)
        )
    ).all()
    counts: dict[str, int] = {chunk_status: count for chunk_status, count in rows}
    total = sum(counts.values())
    progress = calculate_progress(total, counts.get("completed", 0), counts.get("failed", 0))
    return JobRead(
        id=job.id,
        document_id=job.document_id,
        document_revision=job.document_revision,
        status=job.status,
        backend=job.backend,
        model=job.model,
        voice=job.voice,
        speed=job.speed,
        chunking_mode=job.chunking_mode,
        character_limit=job.character_limit,
        error=job.error,
        output_available=bool(job.output_path),
        progress=ProgressRead(
            total=progress.total,
            completed=progress.completed,
            failed=progress.failed,
            processed=progress.processed,
            percent=progress.percent,
        ),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def set_job_state(session: AsyncSession, job_id: str, action: str) -> Job:
    job = await get_job(session, job_id)
    allowed = {
        "pause": ({"queued", "running"}, "paused"),
        "resume": ({"paused", "failed"}, "queued"),
        "cancel": ({"queued", "running", "paused", "failed"}, "cancelled"),
    }
    if action not in allowed:
        raise JobError(f"unknown action: {action}")
    source_states, target = allowed[action]
    if job.status not in source_states:
        raise JobError(f"cannot {action} job in {job.status} state")
    job.status = target
    job.error = None if action == "resume" else job.error
    job.updated_at = utc_now()

    if action == "cancel":
        # Mark all pending/processing chunks as cancelled so the worker
        # won't pick them up and won't overwrite the job status.
        pending_chunks = (
            await session.scalars(
                select(Chunk).where(
                    Chunk.job_id == job.id,
                    Chunk.status.in_({"pending", "processing"}),
                )
            )
        ).all()
        for chunk in pending_chunks:
            chunk.status = "cancelled"
            chunk.updated_at = utc_now()

    if action == "pause":
        # Mark pending chunks as paused so the worker stops picking them up.
        pending_chunks = (
            await session.scalars(
                select(Chunk).where(
                    Chunk.job_id == job.id,
                    Chunk.status == "pending",
                )
            )
        ).all()
        for chunk in pending_chunks:
            chunk.status = "paused"
            chunk.updated_at = utc_now()

    if action == "resume":
        # Return paused/failed/cancelled chunks to pending.
        stale_chunks = (
            await session.scalars(
                select(Chunk).where(
                    Chunk.job_id == job.id,
                    Chunk.status.in_({"paused", "failed", "cancelled"}),
                )
            )
        ).all()
        for chunk in stale_chunks:
            chunk.status = "pending"
            chunk.error = None
            chunk.updated_at = utc_now()

    await session.commit()
    await session.refresh(job)

    # On resume, chunks are already marked pending; the QueueWorker will pick
    # them up in round-robin order.
    return job
