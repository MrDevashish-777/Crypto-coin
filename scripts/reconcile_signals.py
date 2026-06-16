#!/usr/bin/env python3
"""Manually reconcile OPEN advisor signals (e.g. after server downtime)."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.advisor.persistence import reconcile_all_open_signals
from src.database.db import init_db
from src.monitoring.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


async def main() -> int:
    await init_db()
    closed = await reconcile_all_open_signals()
    logger.info("Reconciliation complete: %d signals closed", closed)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
