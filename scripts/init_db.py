"""
Database Initialization Script
Initialize database schema and create tables
"""

import asyncio
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ProgrammingError
from config.settings import settings
from src.database.models import Base
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_database_if_not_exists():
    """Create database if it doesn't exist"""
    try:
        # Parse the database URL
        parsed = urlparse(settings.DATABASE_URL)
        db_name = parsed.path.lstrip('/')
        user_name = parsed.username
        
        # Create URL for postgres database
        postgres_url = settings.DATABASE_URL.replace(f"/{db_name}", "/postgres")
        
        logger.info(f"Original DATABASE_URL: {settings.DATABASE_URL}")
        logger.info(f"Parsed db_name: {db_name}")
        logger.info(f"Postgres URL: {postgres_url}")
        
        # Connect to postgres database
        engine = create_engine(postgres_url, echo=settings.DATABASE_ECHO)
        
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Create the main database if it doesn't exist
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
            exists = result.fetchone()
            
            if not exists:
                logger.info(f"Creating database '{db_name}'...")
                conn.execute(text(f"CREATE DATABASE {db_name}"))
                conn.commit()
                logger.info(f"✓ Database '{db_name}' created successfully")
            else:
                logger.info(f"Database '{db_name}' already exists")
            
            # Also create the user database if it doesn't exist
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{user_name}'"))
            exists = result.fetchone()
            
            if not exists:
                logger.info(f"Creating database '{user_name}'...")
                conn.execute(text(f"CREATE DATABASE {user_name}"))
                conn.commit()
                logger.info(f"✓ Database '{user_name}' created successfully")
            else:
                logger.info(f"Database '{user_name}' already exists")
                
    except Exception as e:
        logger.error(f"✗ Failed to create database: {str(e)}")
        raise


def init_database():
    """Initialize database - create all tables"""
    try:
        # Create database if it doesn't exist
        create_database_if_not_exists()
        
        # Create engine
        engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
        )

        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("✓ Database initialized successfully")

    except Exception as e:
        logger.error(f"✗ Database initialization failed: {str(e)}")
        raise


def drop_database():
    """Drop all tables - use with caution!"""
    try:
        engine = create_engine(settings.DATABASE_URL)
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=engine)
        logger.warning("✓ All tables dropped")

    except Exception as e:
        logger.error(f"✗ Failed to drop tables: {str(e)}")
        raise


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "drop":
        confirm = input("Are you sure? Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            drop_database()
    else:
        init_database()
