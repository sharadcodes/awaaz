from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendSettings(BaseModel):
    base_url: str = "http://localhost:8880/v1"
    api_key: str = "not-needed"
    model: str = "kokoro"
    voice: str = "af_bella"
    timeout_seconds: float = 300.0
    max_characters: int = Field(default=4_000, ge=1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AWAAZ_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "Awaaz"
    database_url: str = "sqlite+aiosqlite:////data/awaaz.db"
    data_dir: Path = Path("/data")
    worker_concurrency: int = Field(default=1, ge=1, le=16)
    worker_poll_seconds: float = Field(default=1.0, ge=0.1)
    worker_round_robin_batch: int = Field(default=1, ge=1, le=100)
    max_retries: int = Field(default=3, ge=0, le=10)
    max_upload_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    openai_backend: str = Field(default="kokoro", pattern="^(supertonic|kokoro|custom)$")
    
    # Celery settings (retained for test suite compatibility; production uses QueueWorker).
    celery_broker_url: str = "amqp://guest:guest@rabbitmq:5672//"
    celery_result_backend: str = "rpc://"
    celery_task_routes: dict = Field(default_factory=dict)
    
    supertonic: BackendSettings = BackendSettings(
        base_url="http://supertonic:7788/v1",
        model="supertonic-3",
        voice="M1",
    )
    kokoro: BackendSettings = BackendSettings(
        base_url="http://kokoro:8880/v1",
        model="kokoro",
        voice="af_bella",
    )
    custom: BackendSettings = BackendSettings()

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


@lru_cache
def get_settings() -> Settings:
    return Settings()
