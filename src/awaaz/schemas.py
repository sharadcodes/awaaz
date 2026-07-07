from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from awaaz.domain.chunking import ChunkingMode


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1)


class DocumentUpdate(BaseModel):
    text: str = Field(min_length=1)
    expected_revision: int = Field(ge=1)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_filename: str | None
    text: str
    revision: int
    author: str | None
    series: str | None
    tags: str | None
    cover_path: str | None
    metadata_json: dict[str, Any] | None
    word_count: int
    created_at: datetime
    updated_at: datetime
    collections: list[str] = Field(serialization_alias="collection_names", default=[])

    @field_validator("collections", mode="before")
    @classmethod
    def _extract_collection_names(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list | tuple):
            return []
        return [getattr(item, "name", str(item)) for item in value]


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    document_ids: list[str] | None = None


class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    document_count: int
    created_at: datetime
    updated_at: datetime


class JobCreate(BaseModel):
    backend: str = Field(default="kokoro", pattern="^(supertonic|kokoro|custom)$")
    model: str | None = None
    voice: str | None = None
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    chunking_mode: ChunkingMode = ChunkingMode.PARAGRAPH
    character_limit: int = Field(default=1_000, ge=1, le=100_000)


class ProgressRead(BaseModel):
    total: int
    completed: int
    failed: int
    processed: int
    percent: float


class JobRead(BaseModel):
    id: str
    document_id: str
    document_revision: int
    status: str
    backend: str
    model: str
    voice: str
    speed: float
    chunking_mode: str
    character_limit: int
    error: str | None
    output_available: bool
    progress: ProgressRead
    created_at: datetime
    updated_at: datetime


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    position: int
    text: str
    status: str
    attempts: int
    error: str | None

