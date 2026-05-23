"""
Database configuration and session management.
This module provides the base SQLAlchemy setup for all services.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Base class for all ORM models
Base = declarative_base()

# Database URL from environment - no default with hardcoded credentials
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Please set it to your PostgreSQL connection string, e.g.: "
        "postgresql+asyncpg://username:password@host:port/database"
    )

# Validate DATABASE_URL format
if not DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://")):
    raise ValueError(
        "DATABASE_URL must be a valid PostgreSQL connection string starting with "
        "'postgresql://' or 'postgresql+asyncpg://'"
    )

# Log connection info (without credentials)
try:
    from urllib.parse import urlparse
    parsed = urlparse(DATABASE_URL)
    logger.info(f"Connecting to database: {parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}")
except Exception as e:
    logger.warning(f"Could not parse DATABASE_URL for logging: {e}")

# Async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session.
    
    Usage:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session_maker() as session:
        yield session
