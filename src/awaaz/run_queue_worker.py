import asyncio
import logging
import sys

from awaaz.adapters.registry import AdapterFactory
from awaaz.config import get_settings
from awaaz.db import create_schema, session_factory
from awaaz.services.queue import QueueWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)


async def main() -> None:
    settings = get_settings()
    await create_schema()
    print("Database schema initialized", flush=True)

    worker = QueueWorker(session_factory, settings, AdapterFactory(settings))
    await worker.recover_abandoned()
    print(
        f"Queue worker started; round-robin batch={settings.worker_round_robin_batch}",
        flush=True,
    )

    while True:
        try:
            processed = await worker.process_once()
        except Exception:
            logger.exception("Worker loop error")
            processed = False
        if not processed:
            await asyncio.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
