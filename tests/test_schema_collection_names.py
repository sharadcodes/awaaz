import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from awaaz.models import Document
from awaaz.schemas import DocumentRead
from awaaz.services.documents import create_collection, update_collection


@pytest.mark.asyncio
async def test_schema_collection_names(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as session:
        doc = Document(title="Doc", text="Hello")
        session.add(doc)
        await session.flush()
        collection = await create_collection(session, "c1")
        await update_collection(session, collection.id, "c1", [doc.id])
        await session.commit()

        result = await session.scalars(select(Document).options(selectinload(Document.collections)))
        loaded = result.first()
        assert loaded is not None
        print("collections attr:", loaded.collections, type(loaded.collections))
        read = DocumentRead.model_validate(loaded)
        assert "c1" in read.collections
        assert "c1" in read.model_dump(by_alias=True)["collection_names"]
