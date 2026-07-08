from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from awaaz.api import openai_router, router
from awaaz.config import get_settings
from awaaz.db import create_schema


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    await create_schema()
    yield


app = FastAPI(title="Awaaz API", version="1.0.2", lifespan=lifespan)
app.include_router(router)
app.include_router(openai_router)
