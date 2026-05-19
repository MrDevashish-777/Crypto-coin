"""Initialize MongoDB connection for the advisor."""

import asyncio
import logging

from src.database.db import init_db, test_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not await test_connection():
        raise SystemExit("MongoDB connection failed — check MONGODB_URI")
    await init_db()
    logger.info("MongoDB ready for advisor")


if __name__ == "__main__":
    asyncio.run(main())
