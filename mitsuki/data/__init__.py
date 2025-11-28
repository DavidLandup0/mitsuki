from mitsuki.config.properties import get_config
from mitsuki.core.enums import DatabaseAdapter as DatabaseAdapterEnum
from mitsuki.data.adapters.base import DatabaseAdapter
from mitsuki.data.adapters.sqlalchemy import SQLAlchemyAdapter, convert_to_async_url
from mitsuki.data.entity import Entity, get_all_entities, get_entity_metadata, is_entity
from mitsuki.data.query import ComparisonOperator, QueryCondition, QueryOperation
from mitsuki.data.query import Query as QueryObject
from mitsuki.data.query_decorators import Modifying, Query
from mitsuki.data.repository import (
    CrudRepository,
    get_database_adapter,
    set_database_adapter,
)
from mitsuki.data.types import (
    UUID,
    Column,
    EntityMetadata,
    Field,
    FieldMetadata,
    Id,
    UUIDv1,
    UUIDv4,
    UUIDv5,
    UUIDv7,
)


def get_sqlalchemy_metadata():
    """
    Get the SQLAlchemy MetaData object from the database adapter.

    This is useful for Alembic migrations to access table definitions.
    If the database adapter hasn't been set up yet, this will create the adapter
    and populate metadata from entity definitions without creating actual database tables.

    Returns:
        sqlalchemy.MetaData: The SQLAlchemy MetaData containing all table definitions

    Raises:
        ValueError: If database adapter is not SQLAlchemyAdapter

    Example:
        # In alembic/env.py
        from mitsuki.data import get_sqlalchemy_metadata
        target_metadata = get_sqlalchemy_metadata()
    """
    from mitsuki.exceptions import DataException

    try:
        adapter = get_database_adapter()
    except DataException:
        # Adapter not initialized yet
        # Create adapter and populate metadata without creating tables
        adapter = SQLAlchemyAdapter()
        set_database_adapter(adapter)

        # Populate metadata by creating Table objects (but not creating actual database tables)
        entities = get_all_entities()
        for entity_class, entity_meta in entities.items():
            adapter._get_or_create_table(entity_meta)

    if not isinstance(adapter, SQLAlchemyAdapter):
        raise ValueError(
            f"Database adapter is not SQLAlchemy. "
            f"Got {type(adapter).__name__}. "
            f"Alembic integration requires SQLAlchemy adapter."
        )
    return adapter.metadata


async def initialize_database():
    """
    Initialize database adapter and create tables for entities.
    Reads configuration from application.yml and sets up database connection.
    """

    config = get_config()

    # Check for database configuration
    database_url = config.get("database.url")
    if not database_url:
        return None

    # Get adapter type
    adapter_type = config.get("database.adapter")

    # Create adapter
    if adapter_type == DatabaseAdapterEnum.SQLALCHEMY:
        database_adapter = SQLAlchemyAdapter()
    else:
        raise ValueError(f"Unknown database adapter: {adapter_type}")

    # Get database configuration
    echo_sql = config.get_bool("database.echo")
    pool_size = config.get("database.pool.size")
    max_overflow = config.get("database.pool.max_overflow")
    pool_timeout = config.get("database.pool.timeout")
    pool_recycle = config.get("database.pool.recycle")
    enable_pooling = config.get_bool("database.pool.enabled")

    # Connect to database with pool configuration
    await database_adapter.connect(
        database_url,
        echo=echo_sql,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        enable_pooling=enable_pooling,
    )

    # Set global adapter for repositories
    set_database_adapter(database_adapter)

    # Create tables for all registered entities
    entities = get_all_entities()

    for entity_class, entity_meta in entities.items():
        await database_adapter.create_table_if_not_exists(entity_meta)

    return database_adapter


__all__ = [
    # Entity
    "Entity",
    "get_entity_metadata",
    "get_all_entities",
    "is_entity",
    # Field markers
    "Id",
    "Column",
    "Field",
    "UUID",
    "UUIDv1",
    "UUIDv4",
    "UUIDv5",
    "UUIDv7",
    # Metadata
    "EntityMetadata",
    "FieldMetadata",
    # Repository
    "CrudRepository",
    "set_database_adapter",
    "get_database_adapter",
    # Query
    "QueryObject",
    "QueryOperation",
    "QueryCondition",
    "ComparisonOperator",
    "Query",
    "Modifying",
    # Adapters
    "DatabaseAdapter",
    "SQLAlchemyAdapter",
    # Initialization
    "initialize_database",
    # SQLAlchemy integration
    "get_sqlalchemy_metadata",
    "convert_to_async_url",
]
