"""
Alembic Environment Configuration

Database migration environment for StateFlow.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import models and settings
from app.core.config import settings
from app.core.database import Base
from app.models import (
    User,
    Role,
    Permission,
    RefreshToken,
    Organization,
    OrganizationMember,
    Workflow,
    WorkflowVersion,
    WorkflowStep,
    RetryPolicy,
    WorkflowExecution,
    StepExecution,
    CompensationExecution,
    ExecutionEvent,
    OutboxEvent,
    IdempotencyRecord,
    WorkerHeartbeat,
    AuditLog,
)

# Alembic Config object
config = context.config

# Set database URL from settings - keep asyncpg for async migrations
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations with a connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Create async engine
    connectable = AsyncEngine(
        engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            future=True,
        )
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())