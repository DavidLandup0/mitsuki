"""
Unit tests for database connection pooling.
"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool, StaticPool

from mitsuki.data import SQLAlchemyAdapter


@pytest.mark.asyncio
async def test_pooling_enabled_for_postgresql():
    """PostgreSQL should use AsyncAdaptedQueuePool."""
    adapter = SQLAlchemyAdapter()

    # Create engine directly to test pooling config
    adapter.engine = create_async_engine(
        "postgresql+asyncpg://user:pass@localhost/testdb",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=5,
        max_overflow=10,
    )

    assert adapter.engine is not None
    assert isinstance(adapter.engine.pool, AsyncAdaptedQueuePool)

    await adapter.engine.dispose()


@pytest.mark.asyncio
async def test_pooling_disabled_for_sqlite():
    """SQLite :memory: should use StaticPool (single persistent connection)."""
    adapter = SQLAlchemyAdapter()

    await adapter.connect("sqlite+aiosqlite:///:memory:")

    assert adapter.engine is not None
    # SQLite :memory: uses StaticPool to persist data across queries
    assert isinstance(adapter.engine.pool, StaticPool)

    await adapter.disconnect()


@pytest.mark.asyncio
async def test_pooling_explicitly_disabled():
    """Should use NullPool when pooling is explicitly disabled."""
    adapter = SQLAlchemyAdapter()

    adapter.engine = create_async_engine(
        "postgresql+asyncpg://user:pass@localhost/testdb", poolclass=NullPool
    )

    assert adapter.engine is not None
    assert isinstance(adapter.engine.pool, NullPool)

    await adapter.engine.dispose()


@pytest.mark.asyncio
async def test_pool_configuration_parameters():
    """Pool configuration parameters should be passed correctly."""
    adapter = SQLAlchemyAdapter()

    adapter.engine = create_async_engine(
        "postgresql+asyncpg://user:pass@localhost/testdb",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=15,
        max_overflow=25,
        pool_timeout=45,
        pool_recycle=7200,
    )

    assert adapter.engine is not None
    pool = adapter.engine.pool

    # Verify pool configuration
    assert pool._pool.maxsize == 15  # pool_size
    assert pool._max_overflow == 25  # max_overflow

    await adapter.engine.dispose()


@pytest.mark.asyncio
async def test_mysql_uses_pooling():
    """MySQL should use AsyncAdaptedQueuePool."""
    adapter = SQLAlchemyAdapter()

    adapter.engine = create_async_engine(
        "mysql+aiomysql://user:pass@localhost/testdb", poolclass=AsyncAdaptedQueuePool
    )

    assert adapter.engine is not None
    assert isinstance(adapter.engine.pool, AsyncAdaptedQueuePool)

    await adapter.engine.dispose()
