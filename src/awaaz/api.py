import asyncio
import json
import shutil
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from awaaz.adapters.registry import AdapterFactory
from awaaz.config import Settings, get_settings
from awaaz.db import get_session
from awaaz.domain.exceptions import AwaazError
from awaaz.models import Chunk, Collection, Document, Job
from awaaz.schemas import (
    ChunkRead,
    CollectionCreate,
    CollectionRead,
    CollectionUpdate,
    DocumentCreate,
    DocumentRead,
    DocumentUpdate,
    JobCreate,
    JobRead,
)
from awaaz.services.documents import (
    create_collection,
    delete_collection,
    delete_document,
    get_document,
    list_collections,
    update_collection,
    update_document_text,
)
from awaaz.services.files import (
    extract_cover,
    extract_metadata,
    extract_text,
    save_upload,
    validate_upload,
)
from awaaz.services.jobs import create_job, get_job, serialize_job, set_job_state

router = APIRouter(prefix="/api/v1")
openai_router = APIRouter(prefix="/v1")


def _bad_request(error: AwaazError | ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/backends")
async def list_backends(settings: Settings = Depends(get_settings)) -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "base_url": backend.base_url,
            "model": backend.model,
            "voice": backend.voice,
            "max_characters": backend.max_characters,
        }
        for name, backend in (
            ("supertonic", settings.supertonic),
            ("kokoro", settings.kokoro),
            ("custom", settings.custom),
        )
    ]


class BackendVoicesResponse(BaseModel):
    backend: str
    voices: list[str]


@router.get("/backends/{name}/voices", response_model=BackendVoicesResponse)
async def list_backend_voices(
    name: str, settings: Settings = Depends(get_settings)
) -> BackendVoicesResponse:
    backend = getattr(settings, name, None)
    if backend is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown backend: {name}"
        )
    # Supertonic exposes /v1/styles, Kokoro exposes /v1/audio/voices.
    # base_url already includes the /v1 prefix (e.g. http://supertonic:7788/v1).
    voices_path = "/styles" if name == "supertonic" else "/audio/voices"
    url = f"{backend.base_url.rstrip('/')}{voices_path}"
    timeout = httpx.Timeout(10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
    except httpx.RequestError:
        # If the engine is unreachable, return an empty list so the UI can still
        # let the user type a custom voice name.
        return BackendVoicesResponse(backend=name, voices=[backend.voice])
    if response.status_code >= 400:
        # If the engine's voice endpoint returns an error, return an empty list
        # rather than propagating a 502/503 to the frontend.
        return BackendVoicesResponse(backend=name, voices=[backend.voice])
    try:
        data = response.json()
    except Exception:
        return BackendVoicesResponse(backend=name, voices=[backend.voice])
    # Supertonic returns {"styles": [{"name": "..."}, ...]}.
    # Kokoro returns {"voices": ["...", ...]}.
    voices: list[str] = []
    for style in data.get("styles", []):
        if isinstance(style, dict) and "name" in style:
            voices.append(str(style["name"]))
    voices.extend(data.get("voices", []))
    return BackendVoicesResponse(backend=name, voices=voices)


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def add_text_document(
    request: DocumentCreate, session: AsyncSession = Depends(get_session)
) -> Document:
    text = request.text.strip()
    document = Document(title=request.title.strip(), text=text, word_count=len(text.split()))
    session.add(document)
    await session.commit()
    await session.refresh(document, ["collections"])
    return document


@router.post("/documents/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Document:
    filename = Path((file.filename or "upload").replace("\\", "/")).name
    try:
        extension = validate_upload(filename)
        stored = settings.uploads_dir / f"{uuid.uuid4()}{extension}"
        await save_upload(file, stored, settings.max_upload_bytes)
        text = await extract_text(stored)
        metadata = await extract_metadata(stored)
        cover_path = None
        cover_target = settings.uploads_dir / f"{uuid.uuid4()}.cover.jpg"
        if await extract_cover(stored, cover_target):
            cover_path = str(cover_target)
    except AwaazError as error:
        raise _bad_request(error) from error
    document = Document(
        title=(title or metadata.get("title") or Path(filename).stem).strip(),
        source_filename=filename,
        text=text.strip(),
        author=_join_authors(metadata.get("authors")),
        series=metadata.get("series"),
        tags=", ".join(metadata.get("tags", [])) if metadata.get("tags") else None,
        cover_path=cover_path,
        metadata_json=metadata,
        word_count=len(text.split()),
    )
    session.add(document)
    await session.commit()
    await session.refresh(document, ["collections"])
    return document


def _join_authors(authors: list[str] | None) -> str | None:
    if not authors:
        return None
    return ", ".join(authors[:3])


@router.get("/documents", response_model=list[DocumentRead])
async def list_documents(
    collection_id: str | None = None,
    author: str | None = None,
    series: str | None = None,
    tag: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[Document]:
    query = select(Document).options(selectinload(Document.collections))
    if collection_id:
        query = (
            query.select_from(Document)
            .join(Document.collections)
            .where(Collection.id == collection_id)
        )
    if author:
        query = query.where(Document.author == author)
    if series:
        query = query.where(Document.series == series)
    if tag:
        query = query.where(Document.tags.contains(tag))
    return list((await session.scalars(query.order_by(Document.created_at.desc()))).all())


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def read_document(document_id: str, session: AsyncSession = Depends(get_session)) -> Document:
    try:
        return await get_document(session, document_id)
    except AwaazError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.put("/documents/{document_id}/text", response_model=DocumentRead)
async def edit_document(
    document_id: str,
    request: DocumentUpdate,
    session: AsyncSession = Depends(get_session),
) -> Document:
    try:
        return await update_document_text(
            session, document_id, request.text, request.expected_revision
        )
    except AwaazError as error:
        raise _bad_request(error) from error


@router.get("/documents/{document_id}/cover")
async def download_cover(
    document_id: str, session: AsyncSession = Depends(get_session)
) -> FileResponse:
    document = await get_document(session, document_id)
    if not document.cover_path or not Path(document.cover_path).is_file():
        raise HTTPException(status_code=404, detail="cover not found")
    return FileResponse(document.cover_path)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(document_id: str, session: AsyncSession = Depends(get_session)) -> None:
    try:
        await delete_document(session, document_id)
    except AwaazError as error:
        raise _bad_request(error) from error


@router.get("/collections", response_model=list[CollectionRead])
async def read_collections(session: AsyncSession = Depends(get_session)) -> list[CollectionRead]:
    rows = await list_collections(session)
    return [
        CollectionRead(
            id=collection.id,
            name=collection.name,
            document_count=count,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )
        for collection, count in rows
    ]


@router.post("/collections", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
async def add_collection(
    request: CollectionCreate, session: AsyncSession = Depends(get_session)
) -> CollectionRead:
    try:
        collection = await create_collection(session, request.name)
    except AwaazError as error:
        raise _bad_request(error) from error
    return CollectionRead(
        id=collection.id,
        name=collection.name,
        document_count=0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.put("/collections/{collection_id}", response_model=CollectionRead)
async def edit_collection(
    collection_id: str,
    request: CollectionUpdate,
    session: AsyncSession = Depends(get_session),
) -> CollectionRead:
    try:
        collection = await update_collection(
            session, collection_id, request.name, request.document_ids
        )
        return CollectionRead(
            id=collection.id,
            name=collection.name,
            document_count=len(collection.documents),
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )
    except AwaazError as error:
        raise _bad_request(error) from error


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collection(
    collection_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    try:
        await delete_collection(session, collection_id)
    except AwaazError as error:
        raise _bad_request(error) from error


@router.post(
    "/documents/{document_id}/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED
)
async def add_job(
    document_id: str,
    request: JobCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> JobRead:
    try:
        document = await get_document(session, document_id)
        job = await create_job(session, document, request, settings)
        return await serialize_job(session, job)
    except (AwaazError, ValueError) as error:
        raise _bad_request(error) from error


@router.get("/jobs", response_model=list[JobRead])
async def list_jobs(session: AsyncSession = Depends(get_session)) -> list[JobRead]:
    jobs = (await session.scalars(select(Job).order_by(Job.created_at.desc()))).all()
    return [await serialize_job(session, job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobRead)
async def read_job(job_id: str, session: AsyncSession = Depends(get_session)) -> JobRead:
    try:
        return await serialize_job(session, await get_job(session, job_id))
    except AwaazError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/jobs/{job_id}/chunks", response_model=list[ChunkRead])
async def list_chunks(job_id: str, session: AsyncSession = Depends(get_session)) -> list[Chunk]:
    await get_job(session, job_id)
    return list(
        (
            await session.scalars(
                select(Chunk).where(Chunk.job_id == job_id).order_by(Chunk.position)
            )
        ).all()
    )


@router.post("/jobs/{job_id}/{action}", response_model=JobRead)
async def control_job(
    job_id: str, action: str, session: AsyncSession = Depends(get_session)
) -> JobRead:
    try:
        return await serialize_job(session, await set_job_state(session, job_id, action))
    except AwaazError as error:
        raise _bad_request(error) from error


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        from awaaz.db import session_factory

        last_payload = ""
        while True:
            async with session_factory() as session:
                try:
                    result = await serialize_job(session, await get_job(session, job_id))
                    payload = result.model_dump(mode="json")
                except AwaazError:
                    yield 'event: error\ndata: {"detail":"job not found"}\n\n'
                    return
            encoded = json.dumps(payload, separators=(",", ":"))
            if encoded != last_payload:
                yield f"event: progress\ndata: {encoded}\n\n"
                last_payload = encoded
            if result.status in {"completed", "failed", "cancelled"}:
                return
            await asyncio.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/jobs/{job_id}/download")
async def download_job(job_id: str, session: AsyncSession = Depends(get_session)) -> FileResponse:
    job = await get_job(session, job_id)
    if not job.output_path or not Path(job.output_path).is_file():
        raise HTTPException(status_code=409, detail="audio output is not ready")
    return FileResponse(job.output_path, media_type="audio/mpeg", filename=f"{job_id}.mp3")


class SpeechRequest(BaseModel):
    model: str | None = None
    input: str = Field(min_length=1, max_length=100_000)
    voice: str | None = None
    response_format: str = Field(default="mp3", pattern="^(mp3|wav)$")
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


@openai_router.post("/audio/speech")
async def speech(
    request: SpeechRequest, settings: Settings = Depends(get_settings)
) -> FileResponse:
    configured = getattr(settings, settings.openai_backend)
    if len(request.input) > configured.max_characters:
        raise HTTPException(
            status_code=400,
            detail=f"input exceeds backend maximum of {configured.max_characters} characters",
        )
    request_id = str(uuid.uuid4())
    directory = settings.audio_dir / "openai" / request_id
    wav = directory / "speech.wav"
    adapter = AdapterFactory(settings).create(
        settings.openai_backend,
        request.model or configured.model,
        request.voice or configured.voice,
    )
    try:
        await adapter.synthesize(request.input, wav, speed=request.speed)
    except AwaazError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    if request.response_format == "wav":
        return FileResponse(wav, media_type="audio/wav", filename="speech.wav")
    mp3 = directory / "speech.mp3"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(wav),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(mp3),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise HTTPException(status_code=502, detail=stderr.decode(errors="replace")[-500:])
    return FileResponse(mp3, media_type="audio/mpeg", filename="speech.mp3")


class PreviewRequest(BaseModel):
    voice: str
    model: str
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    text: str = Field(
        default="Hello! This is a preview of the voice you selected in Awaaz.",
        min_length=1,
        max_length=500,
    )


@router.post("/backends/{name}/preview")
async def preview_voice(
    name: str,
    request: PreviewRequest,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    backend = getattr(settings, name, None)
    if backend is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown backend: {name}"
        )
    if len(request.text) > backend.max_characters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"input exceeds backend maximum of {backend.max_characters} characters",
        )
    request_id = str(uuid.uuid4())
    directory = settings.audio_dir / "previews" / request_id
    directory.mkdir(parents=True, exist_ok=True)
    wav = directory / "preview.wav"
    adapter = AdapterFactory(settings).create(
        name,
        request.model,
        request.voice,
    )
    try:
        await adapter.synthesize(request.text, wav, speed=request.speed)
    except AwaazError as error:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    mp3 = directory / "preview.mp3"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(wav),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(mp3),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=stderr.decode(errors="replace")[-500:],
        )

    background_tasks.add_task(shutil.rmtree, directory, ignore_errors=True)
    return FileResponse(mp3, media_type="audio/mpeg", filename="preview.mp3")
