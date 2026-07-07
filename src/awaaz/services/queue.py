from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from awaaz.adapters.registry import AdapterFactory
from awaaz.config import Settings
from awaaz.domain.exceptions import TtsRequestError
from awaaz.models import Chunk, Job, utc_now
from awaaz.services.audio import assemble_mp3


class QueueWorker:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        settings: Settings,
        adapters: AdapterFactory,
    ) -> None:
        self._sessions = sessions
        self._settings = settings
        self._adapters = adapters

    async def recover_abandoned(self) -> None:
        async with self._sessions() as session:
            await session.execute(
                update(Chunk).where(Chunk.status == "processing").values(status="pending")
            )
            await session.execute(
                update(Job).where(Job.status == "assembling").values(status="running")
            )
            await session.commit()

    async def claim(self) -> Chunk | None:
        async with self._sessions() as session, session.begin():
            statement = (
                select(Chunk)
                .join(Job)
                .where(Chunk.status == "pending", Job.status.in_({"queued", "running"}))
                .order_by(Job.created_at, Chunk.position)
                .with_for_update(skip_locked=True)
                .limit(1)
                .options(selectinload(Chunk.job))
            )
            chunk = await session.scalar(statement)
            if chunk is None:
                return None
            chunk.status = "processing"
            chunk.attempts += 1
            chunk.updated_at = utc_now()
            chunk.job.status = "running"
            chunk.job.updated_at = utc_now()
            return chunk

    async def process_once(self) -> bool:
        chunk = await self.claim()
        if chunk is None:
            ready_job_id = await self._find_ready_job()
            if ready_job_id is None:
                return False
            await self._finish_if_complete(ready_job_id)
            return True
        job = chunk.job
        chunk_dir = self._settings.audio_dir / job.id / "chunks"
        target = chunk_dir / f"{chunk.position:08d}.wav"
        adapter = self._adapters.create(job.backend, job.model, job.voice)
        try:
            await adapter.synthesize(chunk.text, target, speed=job.speed)
        except TtsRequestError as error:
            await self._record_failure(chunk.id, str(error), error.retryable)
            return True
        except Exception as error:  # worker boundary must persist unexpected failures
            await self._record_failure(chunk.id, str(error), False)
            return True
        await self._record_success(chunk.id, target)
        await self._finish_if_complete(job.id)
        return True

    async def _find_ready_job(self) -> str | None:
        incomplete = select(Chunk.id).where(
            Chunk.job_id == Job.id, Chunk.status != "completed"
        ).exists()
        async with self._sessions() as session:
            job_id: str | None = await session.scalar(
                select(Job.id)
                .where(Job.status.in_({"queued", "running"}), ~incomplete)
                .order_by(Job.created_at)
                .limit(1)
            )
            return job_id

    async def _record_failure(self, chunk_id: str, message: str, retryable: bool) -> None:
        async with self._sessions() as session:
            chunk = await session.get(Chunk, chunk_id, options=[selectinload(Chunk.job)])
            if chunk is None:
                return
            if retryable and chunk.attempts <= self._settings.max_retries:
                chunk.status = "pending"
            else:
                chunk.status = "failed"
                chunk.job.status = "failed"
                chunk.job.error = message
            chunk.error = message
            chunk.updated_at = utc_now()
            chunk.job.updated_at = utc_now()
            await session.commit()

    async def _record_success(self, chunk_id: str, target: Path) -> None:
        async with self._sessions() as session:
            chunk = await session.get(Chunk, chunk_id)
            if chunk is None:
                return
            chunk.status = "completed"
            chunk.audio_path = str(target)
            chunk.error = None
            chunk.updated_at = utc_now()
            await session.commit()

    async def _finish_if_complete(self, job_id: str) -> None:
        async with self._sessions() as session, session.begin():
            job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job is None or job.status not in {"queued", "running"}:
                return
            remaining = await session.scalar(
                select(func.count(Chunk.id)).where(
                    Chunk.job_id == job_id, Chunk.status != "completed"
                )
            )
            if remaining:
                return
            job.status = "assembling"
            job.updated_at = utc_now()
        async with self._sessions() as session:
            chunks = (
                await session.scalars(
                    select(Chunk).where(Chunk.job_id == job_id).order_by(Chunk.position)
                )
            ).all()
            output = self._settings.audio_dir / job_id / "audiobook.mp3"
        try:
            await assemble_mp3([Path(chunk.audio_path or "") for chunk in chunks], output)
        except Exception as error:
            async with self._sessions() as session:
                job = await session.get(Job, job_id)
                if job is not None:
                    job.status = "failed"
                    job.error = str(error)
                    job.updated_at = utc_now()
                    await session.commit()
            return
        async with self._sessions() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            job.status = "completed"
            job.output_path = str(output)
            job.updated_at = utc_now()
            await session.commit()
