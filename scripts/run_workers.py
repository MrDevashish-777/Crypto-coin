#!/usr/bin/env python3
"""
Background Workers Runner for CoinDCX Futures Advisor
Runs the market scanner and RL weight optimizer in a separate process.
"""

import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.settings import settings
from src.monitoring.logger import setup_logging
from src.api.routes.advisor import get_advisor_processor, shutdown_advisor_processor
from src.database.db import init_db

setup_logging()
logger = logging.getLogger(__name__)

shutdown_event = asyncio.Event()


async def advisor_market_scanner():
    processor = await get_advisor_processor()
    scan_interval = max(settings.SCAN_INTERVAL, 300)
    while not shutdown_event.is_set():
        try:
            logger.info("Advisor scanner: starting universe scan...")
            results = await processor.scan_universe()
            published = sum(
                1 for r in results if r.get("phase") == "publish" and r.get("ok")
            )
            logger.info("Advisor scanner: published %d signals", published)
        except Exception as exc:
            logger.exception("Advisor scanner error: %s", exc)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=scan_interval)
        except asyncio.TimeoutError:
            pass


async def advisor_signal_reconciler():
    interval = max(settings.ADVISOR_RECONCILE_INTERVAL, 60)
    processor = await get_advisor_processor()
    while not shutdown_event.is_set():
        try:
            from src.advisor.persistence import reconcile_all_open_signals

            closed = await reconcile_all_open_signals(fetcher=processor.data_fetcher)
            if closed:
                logger.info("Signal reconciler: closed %d open signals", closed)
        except Exception as exc:
            logger.exception("Signal reconciler error: %s", exc)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def advisor_weight_optimizer():
    from src.analysis.learning_engine import WeightOptimizer
    optimizer = WeightOptimizer()
    
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=300)
    except asyncio.TimeoutError:
        pass

    while not shutdown_event.is_set():
        try:
            logger.info("Weight optimizer: running RL tuning loop...")
            await optimizer.run_optimization(days=30)
        except Exception as exc:
            logger.exception("Weight optimizer error: %s", exc)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=86400)
        except asyncio.TimeoutError:
            pass


async def startup_tasks():
    logger.info("Initializing database for workers...")
    await init_db()
    
    if settings.ADVISOR_RECONCILE_ON_STARTUP:
        try:
            from src.advisor.persistence import reconcile_all_open_signals
            processor = await get_advisor_processor()
            closed = await reconcile_all_open_signals(fetcher=processor.data_fetcher)
            logger.info("Startup reconciliation: closed %d open signals", closed)
        except Exception as exc:
            logger.exception("Startup signal reconciliation failed: %s", exc)

    tasks = []
    
    if settings.ENABLE_BACKGROUND_SCANNER:
        logger.info("Starting background scanner task...")
        tasks.append(asyncio.create_task(advisor_market_scanner()))
        logger.info("Starting RL optimizer task...")
        tasks.append(asyncio.create_task(advisor_weight_optimizer()))
        
    logger.info("Starting signal reconciler task...")
    tasks.append(asyncio.create_task(advisor_signal_reconciler()))
    
    await asyncio.gather(*tasks)


def main():
    logger.info(f"Starting background workers for {settings.APP_NAME}")
    try:
        asyncio.run(startup_tasks())
    except KeyboardInterrupt:
        logger.info("Workers stopped by user")
        shutdown_event.set()
    except Exception as e:
        logger.error(f"Fatal worker error: {str(e)}")
    finally:
        asyncio.run(shutdown_advisor_processor())

if __name__ == "__main__":
    main()
