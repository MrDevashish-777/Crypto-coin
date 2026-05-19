"""
Decorators - Custom decorators for logging, timing, error handling
"""

import functools
import time
import logging
from typing import Callable, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def timing_decorator(func: Callable) -> Callable:
    """Decorator to measure function execution time"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        logger.debug(f"{func.__name__} took {end - start:.4f} seconds")
        return result
    return wrapper


def error_handler(fallback: Any = None):
    """Decorator to handle exceptions gracefully"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}")
                return fallback
        return wrapper
    return decorator


def retry_decorator(max_retries: int = 3, delay: int = 1):
    """Decorator to retry function on failure"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s...")
                    time.sleep(delay)
        return wrapper
    return decorator


def log_execution(level: int = logging.INFO):
    """Decorator to log function execution"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.log(level, f"Executing {func.__name__}")
            result = func(*args, **kwargs)
            logger.log(level, f"Completed {func.__name__}")
            return result
        return wrapper
    return decorator


def cache_result(ttl_seconds: int = 300):
    """Simple in-memory caching decorator"""
    def decorator(func: Callable) -> Callable:
        cache = {}
        cache_time = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            now = time.time()
            
            if key in cache and (now - cache_time[key]) < ttl_seconds:
                logger.debug(f"Cache hit for {func.__name__}")
                return cache[key]
            
            result = func(*args, **kwargs)
            cache[key] = result
            cache_time[key] = now
            return result
        
        return wrapper
    return decorator
