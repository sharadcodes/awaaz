from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from awaaz.celery_tasks import app, check_job_complete, process_chunk_async
from awaaz.config import Settings
from awaaz.models import Chunk, Document, Job


@pytest.mark.asyncio
async def test_process_chunk_success(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    """Test successful chunk processing with Celery task."""
    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    
    async with sessions() as session:
        document = Document(title="Test", text="Sample text for synthesis")
        session.add(document)
        await session.flush()
        
        job = Job(
            document_id=document.id,
            document_revision=1,
            backend="kokoro",
            model="kokoro",
            voice="af_bella",
            chunking_mode="whole",
            character_limit=100,
        )
        session.add(job)
        await session.flush()
        
        chunk = Chunk(job_id=job.id, position=0, text="Sample text for synthesis")
        session.add(chunk)
        await session.commit()
        chunk_id = chunk.id

    # Mock the adapter synthesis and session factory import
    with patch("awaaz.db.session_factory", sessions):
        with patch("awaaz.celery_tasks.AdapterFactory") as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.synthesize.return_value = None
            mock_factory.return_value.create.return_value = mock_adapter
            
            # Mock check_job_complete to avoid triggering assembly
            with patch("awaaz.celery_tasks.check_job_complete"):
                result = await process_chunk_async(chunk_id)
                
    assert result["status"] == "success"
    assert result["chunk_id"] == chunk_id
    assert "audio_path" in result
    
    # Verify chunk was marked as completed
    async with sessions() as session:
        updated_chunk = await session.get(Chunk, chunk_id)
        assert updated_chunk.status == "completed"
        assert updated_chunk.error is None


@pytest.mark.asyncio
async def test_process_chunk_retryable_error(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    """Test chunk processing with retryable error."""
    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    
    async with sessions() as session:
        document = Document(title="Test", text="Sample text")
        session.add(document)
        await session.flush()
        
        job = Job(
            document_id=document.id,
            document_revision=1,
            backend="kokoro",
            model="kokoro",
            voice="af_bella",
            chunking_mode="whole",
            character_limit=100,
        )
        session.add(job)
        await session.flush()
        
        chunk = Chunk(job_id=job.id, position=0, text="Sample text")
        session.add(chunk)
        await session.commit()
        chunk_id = chunk.id

    # Mock the adapter to raise a retryable error and session factory import
    with patch("awaaz.db.session_factory", sessions):
        with patch("awaaz.celery_tasks.AdapterFactory") as mock_factory:
            from awaaz.domain.exceptions import TtsRequestError
            
            mock_adapter = AsyncMock()
            mock_adapter.synthesize.side_effect = TtsRequestError("Temporary error", retryable=True)
            mock_factory.return_value.create.return_value = mock_adapter
            
            with patch("awaaz.celery_tasks.check_job_complete"):
                result = await process_chunk_async(chunk_id)
                
    assert result["status"] == "error"
    assert result["retryable"] is True
    
    # Verify chunk was marked as pending for retry
    async with sessions() as session:
        updated_chunk = await session.get(Chunk, chunk_id)
        assert updated_chunk.status == "pending"
        assert updated_chunk.error == "Temporary error"


@pytest.mark.asyncio
async def test_process_chunk_non_retryable_error(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    """Test chunk processing with non-retryable error."""
    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    
    async with sessions() as session:
        document = Document(title="Test", text="Sample text")
        session.add(document)
        await session.flush()
        
        job = Job(
            document_id=document.id,
            document_revision=1,
            backend="kokoro",
            model="kokoro",
            voice="af_bella",
            chunking_mode="whole",
            character_limit=100,
        )
        session.add(job)
        await session.flush()
        
        chunk = Chunk(job_id=job.id, position=0, text="Sample text")
        session.add(chunk)
        await session.commit()
        chunk_id = chunk.id

    # Mock the adapter to raise a non-retryable error and session factory import
    with patch("awaaz.db.session_factory", sessions):
        with patch("awaaz.celery_tasks.AdapterFactory") as mock_factory:
            from awaaz.domain.exceptions import TtsRequestError
            
            mock_adapter = AsyncMock()
            mock_adapter.synthesize.side_effect = TtsRequestError("Permanent error", retryable=False)
            mock_factory.return_value.create.return_value = mock_adapter
            
            with patch("awaaz.celery_tasks.check_job_complete"):
                result = await process_chunk_async(chunk_id)
                
    assert result["status"] == "error"
    assert result["retryable"] is False
    
    # Verify chunk and job were marked as failed
    async with sessions() as session:
        updated_chunk = await session.get(Chunk, chunk_id)
        await session.refresh(updated_chunk)
        assert updated_chunk.status == "failed"
        assert updated_chunk.error == "Permanent error"


@pytest.mark.asyncio
async def test_check_job_complete_triggers_assembly(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    """Test that check_job_complete triggers assembly when all chunks are complete."""
    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    
    async with sessions() as session:
        document = Document(title="Test", text="First chunk\n\nSecond chunk")
        session.add(document)
        await session.flush()
        
        job = Job(
            document_id=document.id,
            document_revision=1,
            backend="kokoro",
            model="kokoro",
            voice="af_bella",
            chunking_mode="whole",
            character_limit=50,
        )
        session.add(job)
        await session.flush()
        
        chunk1 = Chunk(job_id=job.id, position=0, text="First chunk", status="completed")
        chunk2 = Chunk(job_id=job.id, position=1, text="Second chunk", status="completed")
        session.add_all([chunk1, chunk2])
        await session.commit()
        job_id = job.id

    # Mock assemble_audio to avoid actual file operations and session factory
    with patch("awaaz.db.session_factory", sessions):
        with patch("awaaz.celery_tasks.assemble_audio") as mock_assemble:
            mock_assemble.delay = MagicMock()
            await check_job_complete(job_id)
            
            # Verify assemble_audio was called
            mock_assemble.delay.assert_called_once_with(job_id)


@pytest.mark.asyncio
async def test_check_job_complete_incomplete_job(
    sessions: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    """Test that check_job_complete does not trigger assembly when chunks are pending."""
    settings = Settings(database_url="sqlite+aiosqlite://", data_dir=tmp_path)
    
    async with sessions() as session:
        document = Document(title="Test", text="First chunk\n\nSecond chunk")
        session.add(document)
        await session.flush()
        
        job = Job(
            document_id=document.id,
            document_revision=1,
            backend="kokoro",
            model="kokoro",
            voice="af_bella",
            chunking_mode="whole",
            character_limit=50,
        )
        session.add(job)
        await session.flush()
        
        chunk1 = Chunk(job_id=job.id, position=0, text="First chunk", status="completed")
        chunk2 = Chunk(job_id=job.id, position=1, text="Second chunk", status="pending")
        session.add_all([chunk1, chunk2])
        await session.commit()
        job_id = job.id

    # Mock assemble_audio to verify it's NOT called and session factory
    with patch("awaaz.db.session_factory", sessions):
        with patch("awaaz.celery_tasks.assemble_audio") as mock_assemble:
            mock_assemble.delay = MagicMock()
            await check_job_complete(job_id)
            
            # Verify assemble_audio was NOT called
            mock_assemble.delay.assert_not_called()


def test_celery_app_configuration() -> None:
    """Test that Celery app is properly configured."""
    assert app.main == "awaaz"
    assert app.conf.task_track_started is True
    assert app.conf.worker_prefetch_multiplier == 1