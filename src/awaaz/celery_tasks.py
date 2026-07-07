import concurrent.futures
from pathlib import Path

from celery import Celery
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from awaaz.adapters.registry import AdapterFactory
from awaaz.config import get_settings
from awaaz.domain.exceptions import TtsRequestError
from awaaz.models import Chunk, Job, utc_now
from awaaz.services.audio import assemble_mp3

settings = get_settings()

app = Celery(
    "awaaz",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    task_routes=settings.celery_task_routes,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_default_queue='celery',  # Set default queue
)

# Use eager mode for in-memory broker (tests / local dev without RabbitMQ).
if settings.celery_broker_url.startswith("memory://"):
    app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )


async def process_chunk_async(chunk_id: str) -> dict:
    """Process a single chunk through TTS synthesis (async version for testing)."""
    from awaaz.db import session_factory

    async with session_factory() as session:
        chunk = await session.get(
            Chunk, chunk_id, options=[selectinload(Chunk.job)]
        )
        if chunk is None:
            return {"status": "error", "message": "Chunk not found"}

        job = chunk.job

        # Abort if the chunk was cancelled or paused while waiting in the queue.
        if chunk.status in {"cancelled", "paused"}:
            return {"status": "skipped", "message": f"chunk is {chunk.status}"}

        # Abort if the job was cancelled or paused — don't overwrite job status.
        if job.status in {"cancelled", "paused"}:
            if chunk.status == "pending":
                chunk.status = job.status  # propagate to chunk
                chunk.updated_at = utc_now()
                await session.commit()
            return {"status": "skipped", "message": f"job is {job.status}"}

        chunk_dir = settings.audio_dir / job.id / "chunks"
        target = chunk_dir / f"{chunk.position:08d}.wav"

        # Update status to processing
        chunk.status = "processing"
        chunk.attempts += 1
        chunk.updated_at = utc_now()
        job.status = "running"
        job.updated_at = utc_now()
        await session.commit()

        # Create adapter and synthesize
        adapter = AdapterFactory(settings).create(
            job.backend, job.model, job.voice
        )

        try:
            await adapter.synthesize(chunk.text, target, speed=job.speed)
        except TtsRequestError as error:
            if error.retryable and chunk.attempts <= settings.max_retries:
                chunk.status = "pending"
            else:
                chunk.status = "failed"
                job.status = "failed"
                job.error = str(error)
            chunk.error = str(error)
            chunk.updated_at = utc_now()
            job.updated_at = utc_now()
            await session.commit()
            return {
                "status": "error",
                "message": str(error),
                "retryable": error.retryable,
            }
        except Exception as error:
            chunk.status = "failed"
            job.status = "failed"
            job.error = str(error)
            chunk.error = str(error)
            chunk.updated_at = utc_now()
            job.updated_at = utc_now()
            await session.commit()
            return {"status": "error", "message": str(error), "retryable": False}

        # Re-check job status before marking success — it may have been
        # cancelled while we were synthesizing.
        await session.refresh(job)
        if job.status == "cancelled":
            chunk.status = "cancelled"
            chunk.updated_at = utc_now()
            await session.commit()
            return {"status": "skipped", "message": "job was cancelled during synthesis"}

        # Record success
        chunk.status = "completed"
        chunk.audio_path = str(target)
        chunk.error = None
        chunk.updated_at = utc_now()
        await session.commit()

        # Check if job is complete
        await check_job_complete(job.id)

        return {
            "status": "success",
            "chunk_id": chunk_id,
            "audio_path": str(target),
        }


@app.task(bind=True, max_retries=settings.max_retries)
def process_chunk(self, chunk_id: str) -> dict:
    """Process a single chunk through TTS synthesis."""
    import asyncio

    try:
        asyncio.get_running_loop()
        # If we're in an async context, we need to await the coroutine
        # But since this is a sync function, we'll create a task
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, process_chunk_async(chunk_id))
            return future.result()
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(process_chunk_async(chunk_id))


@app.task
def assemble_audio(job_id: str) -> dict:
    """Assemble all chunks into final audiobook."""
    import asyncio

    from awaaz.db import session_factory

    async def _assemble() -> dict:
        async with session_factory() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return {"status": "error", "message": "Job not found"}

            # Bail if the job was cancelled or paused while assembly was queued.
            if job.status in {"cancelled", "paused"}:
                return {"status": "skipped", "message": f"job is {job.status}"}

            # Update status to assembling
            job.status = "assembling"
            job.updated_at = utc_now()
            await session.commit()

            # Get all completed chunks
            chunks = (
                await session.scalars(
                    select(Chunk)
                    .where(Chunk.job_id == job_id, Chunk.status == "completed")
                    .order_by(Chunk.position)
                )
            ).all()

            if not chunks:
                job.status = "failed"
                job.error = "No completed chunks found"
                job.updated_at = utc_now()
                await session.commit()
                return {"status": "error", "message": "No completed chunks found"}

            # Assemble MP3
            output = settings.audio_dir / job_id / "audiobook.mp3"
            try:
                await assemble_mp3(
                    [Path(chunk.audio_path or "") for chunk in chunks], output
                )
            except Exception as error:
                job.status = "failed"
                job.error = str(error)
                job.updated_at = utc_now()
                await session.commit()
                return {"status": "error", "message": str(error)}

            # Mark job as completed
            job.status = "completed"
            job.output_path = str(output)
            job.updated_at = utc_now()
            await session.commit()

            return {
                "status": "success",
                "job_id": job_id,
                "output_path": str(output),
            }

    try:
        asyncio.get_running_loop()
        # If we're in an async context, we need to use a thread executor
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _assemble())
            return future.result()
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(_assemble())


async def check_job_complete(job_id: str) -> None:
    """Check if all chunks for a job are complete and trigger assembly."""
    from awaaz.db import session_factory

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        # Don't assemble if the job was cancelled or paused.
        if job.status in {"cancelled", "paused"}:
            return

        remaining = await session.scalar(
            select(func.count(Chunk.id)).where(
                Chunk.job_id == job_id, Chunk.status != "completed"
            )
        )

        if remaining == 0:
            # All chunks complete, trigger assembly
            assemble_audio.delay(job_id)