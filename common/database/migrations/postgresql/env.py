"""
Alembic environment configuration for async SQLAlchemy.
This file is configured to work with asyncpg and load models from common/src/models.py
"""
import asyncio
from logging.config import fileConfig
import os
import sys

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Constants for repeated string literals
DATABASE_URL_ENV_VAR = "DATABASE_URL"
SQLALCHEMY_URL_CONFIG = "sqlalchemy.url"
SQLALCHEMY_PREFIX = "sqlalchemy."

# Add the project root to sys.path efficiently
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import Base and models for autogenerate support
try:
    from database.connection import Base
    from database import models
except ImportError as e:
    # Log error for better debugging in CI
    print(f"Error importing modules: {e}")
    print(f"sys.path: {sys.path}")
    raise e

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url from environment
database_url = os.getenv(DATABASE_URL_ENV_VAR)
if database_url:
    config.set_main_option(SQLALCHEMY_URL_CONFIG, database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option(SQLALCHEMY_URL_CONFIG)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Helper function to run migrations with a connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode using asyncpg."""
    # Ensure DATABASE_URL is in the configuration passed to the engine
    section = config.get_section(config.config_ini_section, {}).copy()
    
    # Use the database_url we already extracted or get it again
    db_url = os.getenv(DATABASE_URL_ENV_VAR)
    if db_url:
        section[SQLALCHEMY_URL_CONFIG] = db_url

    connectable = async_engine_from_config(
        section,
        prefix=SQLALCHEMY_PREFIX,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async support."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
