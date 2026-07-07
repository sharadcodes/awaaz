import logging

from awaaz.config import get_settings
from awaaz.db import create_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    await create_schema()
    logger.info("Database schema initialized")
    logger.info("Starting Celery worker with broker: %s", settings.celery_broker_url)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

