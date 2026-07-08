from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from awaaz.domain.exceptions import DocumentError
from awaaz.models import Collection, Document, Job, document_collections, utc_now


async def get_document(session: AsyncSession, document_id: str) -> Document:
    document = await session.scalar(
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.collections))
    )
    if document is None:
        raise DocumentError("document not found")
    return document


async def update_document_text(
    session: AsyncSession, document_id: str, text: str, expected_revision: int
) -> Document:
    if not text.strip():
        raise DocumentError("text cannot be empty")
    document = await get_document(session, document_id)
    if document.revision != expected_revision:
        raise DocumentError("document revision conflict")
    active = await session.scalar(
        select(Job.id).where(
            Job.document_id == document_id,
            Job.status.in_({"queued", "running", "paused"}),
        )
    )
    if active is not None:
        raise DocumentError("cancel active jobs before editing text")
    document.text = text.strip()
    document.word_count = len(document.text.split())
    document.revision += 1
    document.updated_at = utc_now()
    await session.commit()
    await session.refresh(document, ["collections"])
    return document


async def list_documents_with_jobs(session: AsyncSession) -> list[Document]:
    return list(
        (
            await session.scalars(
                select(Document)
                .options(selectinload(Document.collections))
                .order_by(Document.created_at.desc())
            )
        ).all()
    )


async def get_collection(session: AsyncSession, collection_id: str) -> Collection:
    collection = await session.scalar(
        select(Collection)
        .where(Collection.id == collection_id)
        .options(selectinload(Collection.documents))
    )
    if collection is None:
        raise DocumentError("collection not found")
    return collection


async def list_collections(session: AsyncSession) -> list[tuple[Collection, int]]:
    rows = await session.execute(
        select(Collection, func.count(document_collections.c.document_id))
        .select_from(Collection)
        .outerjoin(document_collections, Collection.id == document_collections.c.collection_id)
        .group_by(Collection.id)
        .order_by(Collection.name)
    )
    return [(collection, count) for collection, count in rows.all()]


async def create_collection(session: AsyncSession, name: str) -> Collection:
    collection = Collection(name=name.strip())
    session.add(collection)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise DocumentError("collection name must be unique") from error
    await session.refresh(collection)
    return collection


async def update_collection(
    session: AsyncSession, collection_id: str, name: str | None, document_ids: list[str] | None
) -> Collection:
    collection = await get_collection(session, collection_id)
    if name is not None:
        collection.name = name.strip()
    if document_ids is not None:
        documents = await session.scalars(select(Document).where(Document.id.in_(document_ids)))
        collection.documents = list(documents.all())
    collection.updated_at = utc_now()
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise DocumentError("collection name must be unique") from error
    return collection


async def delete_collection(session: AsyncSession, collection_id: str) -> None:
    collection = await get_collection(session, collection_id)
    await session.delete(collection)
    await session.commit()


async def delete_document(session: AsyncSession, document_id: str) -> None:
    document = await get_document(session, document_id)
    active = await session.scalar(
        select(Job.id).where(
            Job.document_id == document_id,
            Job.status.in_({"queued", "running", "paused"}),
        )
    )
    if active is not None:
        raise DocumentError("cancel active jobs before deleting")
    await session.delete(document)
    await session.commit()
