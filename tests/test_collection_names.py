import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from awaaz.models import Document
from awaaz.services.documents import create_collection, update_collection


@pytest.mark.asyncio
async def test_document_collection_names_are_loaded(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as session:
        doc = Document(title="Doc", text="Hello")
        session.add(doc)
        await session.flush()
        collection = await create_collection(session, "c1")
        await update_collection(session, collection.id, "c1", [doc.id])

        result = await session.scalars(select(Document).options(selectinload(Document.collections)))
        loaded = result.first()
        assert loaded is not None
        print("loaded collections:", loaded.collections)
        names = [c.name for c in loaded.collections]
        assert "c1" in names
