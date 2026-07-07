import atexit
import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

# Create a writable test environment before importing the app, because
# awaaz.db builds the SQLAlchemy engine at module import time.
_test_dir = tempfile.mkdtemp(prefix="awaaz-test-")
os.environ["AWAAZ_DATA_DIR"] = _test_dir
os.environ["AWAAZ_DATABASE_URL"] = "sqlite+aiosqlite://"
atexit.register(shutil.rmtree, _test_dir, ignore_errors=True)

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from awaaz.db import get_session
from awaaz.main import app
from awaaz.models import Base


@pytest_asyncio.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[TestClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()
