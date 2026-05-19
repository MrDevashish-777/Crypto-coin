"""
Logging Configuration Module
Setup structured logging for the application
"""

import logging
import logging.handlers
from pathlib import Path
import sys
from config.settings import settings


def setup_logging():
    """Configure application logging"""

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    log_format = (settings.LOG_FORMAT or "").strip()
    mode = log_format.lower()
    if mode == "json":
        from pythonjsonlogger import jsonlogger
        console_format = jsonlogger.JsonFormatter()
    elif mode in {"console", "text", "plain", "default", ""}:
        # Support mode-style env values (e.g., LOG_FORMAT=console).
        console_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        console_format = logging.Formatter(log_format)
        
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    if settings.LOG_TO_FILE:
        # Create logs directory only when file logging is enabled.
        log_dir = Path(settings.LOG_FILE).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
        file_handler.setFormatter(console_format)
        logger.addHandler(file_handler)

    logger.info(
        f"Logging configured - Level: {settings.LOG_LEVEL}, "
        f"file_logging={'enabled' if settings.LOG_TO_FILE else 'disabled'}"
    )
