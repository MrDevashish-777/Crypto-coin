#!/usr/bin/env python3
"""
Application Startup Script
Run the Crypto Trading Signal Server
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
import logging
from src.api.server import app
import uvicorn
from config.settings import settings

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)

logger = logging.getLogger(__name__)


async def startup_tasks():
    """Run startup tasks"""
    logger.info("Running startup tasks...")
    
    # Test database connection
    logger.info("Checking database connection...")
    
    logger.info("Checking CoinDCX API connection...")
    from src.data.data_fetcher import DataFetcher
    fetcher = DataFetcher()
    is_connected = await fetcher.test_connection()

    if is_connected:
        logger.info("✓ CoinDCX API connection successful")
    else:
        logger.warning("✗ CoinDCX API connection failed - signals may not generate")
    
    await fetcher.close()
    
    logger.info("Startup tasks completed")


def main():
    """Main entry point"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"Server: {settings.SERVER_HOST}:{settings.SERVER_PORT}")
    logger.info(f"Workers: {settings.WORKERS}")

    # Run startup tasks
    try:
        asyncio.run(startup_tasks())
    except Exception as e:
        logger.error(f"Startup tasks failed: {str(e)}")
        # Continue anyway - some features may not be available

    # Start ASGI server
    uvicorn.run(
        app,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        workers=settings.WORKERS if settings.ENV == "production" else 1,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)
