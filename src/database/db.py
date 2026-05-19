"""
MongoDB connection manager for Crypto Bot.
Replaces the old SQLAlchemy/PostgreSQL implementation.
Uses Motor (async MongoDB driver) connected to MongoDB Atlas.
"""
from __future__ import annotations

import logging
import os

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

MONGODB_URI: str = os.environ.get(
    "MONGODB_URI",
    "mongodb://localhost:27017",
)
MONGODB_DB_NAME: str = os.environ.get("MONGODB_DB_NAME", "planitt")


async def get_db() -> AsyncIOMotorDatabase:
    """Return the shared MongoDB database handle (singleton)."""
    global _client, _db
    if _client is None:
        _client = AsyncIOMotorClient(
            MONGODB_URI,
            # Connection pool tuned for Render Starter (512 MB RAM)
            maxPoolSize=50,
            minPoolSize=5,
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=20_000,
        )
        _db = _client[MONGODB_DB_NAME]
        logger.info("✓ MongoDB client created for Crypto Bot (db=%s)", MONGODB_DB_NAME)
    return _db


async def init_db() -> None:
    """Index lifecycle is centralized in ``scripts/ensure_indexes.py`` (CI / deploy hook).

    Crypto-specific compound indexes on ``signals`` / ``news`` are created there together
    with the rest of Planitt so definitions do not drift across services.
    """
    await get_db()
    logger.info("Crypto Bot: skipping per-service index creation (use scripts/ensure_indexes.py).")


async def close_db() -> None:
    """Gracefully close the MongoDB connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")


async def test_connection() -> bool:
    """Ping MongoDB — used in startup health check."""
    try:
        db = await get_db()
        await db.command("ping")
        logger.info("✓ MongoDB connection successful")
        return True
    except Exception as exc:
        logger.error("✗ MongoDB connection failed: %s", exc)
        return False


