#!/usr/bin/env python3
"""One-shot CoinDCX advisor universe scan (CLI)."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.settings import settings
from src.advisor.processor import AdvisorProcessor

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL), format=settings.LOG_FORMAT)
logger = logging.getLogger(__name__)


async def main() -> None:
    proc = AdvisorProcessor()
    ok = await proc.data_fetcher.test_connection()
    if not ok:
        logger.error("CoinDCX unreachable — aborting scan")
        sys.exit(1)
    results = await proc.scan_universe()
    published = [r for r in results if r.get("ok")]
    logger.info("Scan complete: %d published / %d attempts", len(published), len(results))
    for r in published:
        sig = r.get("signal", {})
        logger.info(
            "  %s %s %s → %s",
            sig.get("symbol"),
            sig.get("timeframe"),
            sig.get("direction"),
            r.get("pdf_path"),
        )
    await proc.close()


if __name__ == "__main__":
    asyncio.run(main())
