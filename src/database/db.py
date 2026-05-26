"""
MongoDB connection manager — Motor async client (Atlas or local).
"""
from __future__ import annotations

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config.settings import settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def _mongo_uri() -> str:
    return settings.MONGODB_URI


def _mongo_db_name() -> str:
    return settings.MONGODB_DB_NAME


async def get_db() -> AsyncIOMotorDatabase:
    """Return the shared MongoDB database handle (singleton)."""
    global _client, _db
    if _client is None:
        uri = _mongo_uri()
        db_name = _mongo_db_name()
        client_options = {
            "maxPoolSize": settings.MONGODB_MAX_POOL_SIZE,
            "minPoolSize": settings.MONGODB_MIN_POOL_SIZE,
            "serverSelectionTimeoutMS": settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            "connectTimeoutMS": settings.MONGODB_CONNECT_TIMEOUT_MS,
            "socketTimeoutMS": settings.MONGODB_SOCKET_TIMEOUT_MS,
            "retryReads": True,
            "retryWrites": True,
        }

        # Atlas requires TLS; certifi avoids trust-store edge cases on some macOS setups.
        if uri.startswith("mongodb+srv://"):
            try:
                import certifi

                client_options["tlsCAFile"] = certifi.where()
            except Exception:
                logger.warning("certifi not available; using system CA for Atlas TLS")

        _client = AsyncIOMotorClient(uri, **client_options)
        _db = _client[db_name]
        host_hint = "Atlas" if uri.startswith("mongodb+srv://") else uri.split("@")[-1][:40]
        logger.info("MongoDB client created (db=%s, host=%s)", db_name, host_hint)
    return _db


async def init_db() -> None:
    await get_db()
    logger.info("MongoDB ready (index creation optional via scripts/ensure_indexes.py)")


async def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")


async def test_connection() -> bool:
    try:
        db = await get_db()
        await db.command("ping")
        logger.info("MongoDB connection successful")
        return True
    except Exception as exc:
        if _mongo_uri().startswith("mongodb+srv://"):
            logger.error(
                "MongoDB Atlas connection failed. Verify Atlas Network Access allows this machine IP "
                "and connection URI credentials are correct."
            )
        logger.error("MongoDB connection failed: %s", exc)
        return False
