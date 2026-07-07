from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from awaaz.config import get_settings

settings = get_settings()

# Configure engine based on database type
if settings.database_url.startswith("sqlite"):
    engine = create_async_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def create_schema() -> None:
    """Apply database schema via Alembic migrations.

    Existing databases created by the legacy ``Base.metadata.create_all``
    flow are detected and stamped to the initial revision before upgrading,
    so the migration history is adopted without data loss.
    """
    await _adopt_legacy_schema()
    await _run_alembic_upgrade()


async def _adopt_legacy_schema() -> None:
    """Stamp legacy (pre-Alembic) databases to the initial revision."""
    from alembic import command
    from alembic.config import Config

    async with engine.connect() as connection:
        def _inspect(conn: Connection) -> dict[str, Any]:
            inspector = inspect(conn)
            table_names = set(inspector.get_table_names())
            return {
                "has_alembic_version": "alembic_version" in table_names,
                "has_legacy_tables": bool(
                    table_names & {"documents", "jobs", "chunks", "collections"}
                ),
            }

        state = await connection.run_sync(_inspect)

    if state["has_alembic_version"] or not state["has_legacy_tables"]:
        return

    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(alembic_ini))
    async with engine.begin() as connection:
        def _stamp(conn: Connection) -> None:
            cfg.attributes["connection"] = conn
            command.stamp(cfg, "head")

        await connection.run_sync(_stamp)


async def _run_alembic_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    async with engine.begin() as connection:
        def _upgrade(conn: Connection) -> None:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")

        await connection.run_sync(_upgrade)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
