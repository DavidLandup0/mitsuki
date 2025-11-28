"""
SQLAlchemy database adapter implementation.
Uses SQLAlchemy Core (not ORM) for flexibility and async support.
"""

import re
import uuid as uuid_module
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Time,
    and_,
    delete,
    func,
    insert,
    or_,
    select,
    text,
    update,
)
from sqlalchemy import Column as SAColumn
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool, StaticPool
from sqlalchemy.types import CHAR, TypeDecorator

from mitsuki.core.enums import DatabaseDialect, SQLOperation
from mitsuki.data.adapters.base import DatabaseAdapter
from mitsuki.data.entity import get_entity_metadata
from mitsuki.data.query import ComparisonOperator, LogicalOperator, Query
from mitsuki.data.types import EntityMetadata, FieldMetadata
from mitsuki.exceptions import DatabaseNotConnectedException, DataException


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type for PostgreSQL, otherwise uses CHAR(36) storing as strings.
    """

    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == DatabaseDialect.POSTGRESQL:
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == DatabaseDialect.POSTGRESQL:
            return value  # PostgreSQL handles UUID natively
        else:
            # Convert UUID to string for other databases
            if isinstance(value, uuid_module.UUID):
                return str(value)
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == DatabaseDialect.POSTGRESQL:
            return value  # PostgreSQL returns UUID objects
        else:
            # Convert string to UUID for other databases
            if isinstance(value, str):
                return uuid_module.UUID(value)
            return value


def convert_to_async_url(connection_string: str) -> str:
    """
    Convert a sync database URL to an async-compatible URL.

    Args:
        connection_string: Database URL (e.g., postgresql://...)

    Returns:
        Async-compatible database URL (e.g., postgresql+asyncpg://...)
    """
    if connection_string.startswith("postgresql://"):
        return connection_string.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif connection_string.startswith("mysql://"):
        return connection_string.replace("mysql://", "mysql+aiomysql://", 1)
    elif connection_string.startswith("sqlite://"):
        return connection_string.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return connection_string


class SQLAlchemyAdapter(DatabaseAdapter):
    """
    SQLAlchemy-based database adapter with async support.
    Uses SQLAlchemy Core for direct SQL generation.
    """

    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.metadata = MetaData()
        self._tables: Dict[str, Table] = {}  # Cache of table objects

    async def connect(
        self,
        connection_string: str,
        echo: bool = False,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        enable_pooling: bool = True,
    ) -> None:
        """
        Connect to database using async SQLAlchemy.

        Args:
            connection_string: Database URL (e.g., postgresql+asyncpg://...)
            echo: Enable SQL query logging
            pool_size: Number of connections to maintain in the pool (default: 10)
            max_overflow: Maximum number of connections beyond pool_size (default: 20)
            pool_timeout: Seconds to wait before giving up on connection (default: 30)
            pool_recycle: Seconds before recycling connections (default: 3600)
            enable_pooling: Enable connection pooling (default: True, disable for SQLite)
        """
        # Convert sync connection strings to async
        connection_string = convert_to_async_url(connection_string)

        if connection_string.startswith("sqlite"):
            enable_pooling = False

        # Disable pooling for SQLite (check again for already-async connection strings)
        # BUT: :memory: databases need StaticPool to persist across queries
        if "sqlite" in connection_string:
            if ":memory:" in connection_string:
                # Use StaticPool for :memory: databases (single persistent connection)
                self.engine = create_async_engine(
                    connection_string, poolclass=StaticPool, echo=echo
                )
            else:
                # Use NullPool for file-based SQLite
                self.engine = create_async_engine(
                    connection_string, poolclass=NullPool, echo=echo
                )
        elif enable_pooling:
            # Use connection pooling for PostgreSQL, MySQL, etc.
            self.engine = create_async_engine(
                connection_string,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
                echo=echo,
            )
        else:
            # Pooling explicitly disabled
            self.engine = create_async_engine(
                connection_string, poolclass=NullPool, echo=echo
            )

        # Test connection
        async with self.engine.connect() as conn:
            await conn.execute(select(1))

    async def disconnect(self) -> None:
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
        self._tables.clear()

    def _get_sqlalchemy_type(self, field_meta: FieldMetadata):
        """Convert field metadata to SQLAlchemy column type"""
        db_type = field_meta.db_type.upper()

        if db_type == "UUID":
            # Use our custom GUID type that handles both PostgreSQL and SQLite
            return GUID()
        elif db_type.startswith("INTEGER"):
            return Integer
        elif db_type.startswith("VARCHAR"):
            # Use max_length if specified, otherwise extract from db_type or use default
            if field_meta.max_length is not None:
                return String(field_meta.max_length)
            elif "(" in db_type:
                length = int(db_type.split("(")[1].split(")")[0])
                return String(length)
            return String(255)
        elif db_type.startswith("TEXT"):
            return Text
        elif db_type.startswith("FLOAT"):
            return Float
        elif db_type.startswith("BOOLEAN"):
            return Boolean
        elif db_type.startswith("TIMESTAMP") or db_type.startswith("DATETIME"):
            return DateTime
        elif db_type.startswith("DATE"):
            return Date
        elif db_type.startswith("TIME"):
            return Time
        else:
            return Text  # Default fallback

    def _get_or_create_table(self, entity_meta: EntityMetadata) -> Table:
        """Get or create a SQLAlchemy Table object for an entity"""
        table_name = entity_meta.table_name

        if table_name in self._tables:
            return self._tables[table_name]

        # Build columns
        columns = []
        for field_name, field_meta in entity_meta.fields.items():
            sa_type = self._get_sqlalchemy_type(field_meta)

            col = SAColumn(
                field_name,
                sa_type,
                primary_key=field_meta.primary_key,
                autoincrement=field_meta.auto_increment,
                nullable=field_meta.nullable,
                unique=field_meta.unique,
                index=field_meta.index,
                default=field_meta.default,
            )
            columns.append(col)

        table = Table(table_name, self.metadata, *columns)
        self._tables[table_name] = table

        # Attach metadata to entity class for Alembic integration
        entity_meta.entity_class.metadata = self.metadata

        return table

    def get_table(self, entity_type: type) -> Table:
        """
        Get SQLAlchemy Table object for an entity type.

        Args:
            entity_type: The entity class decorated with @Entity

        Returns:
            Table: SQLAlchemy Table object

        Example:
            from models import User, Post
            user_table = adapter.get_table(User)
            post_table = adapter.get_table(Post)
        """
        entity_meta = get_entity_metadata(entity_type)
        return self._get_or_create_table(entity_meta)

    def get_connection(self):
        """
        Get a database connection as a context manager.
        Connection is automatically closed when exiting the context.

        Usage:
            async with adapter.get_connection() as conn:
                result = await conn.execute(query)

        Returns:
            AsyncConnection context manager
        """
        return self.engine.connect()

    async def create_table_if_not_exists(self, entity_meta: EntityMetadata) -> None:
        """Create table for entity if it doesn't exist"""
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        table = self._get_or_create_table(entity_meta)

        async with self.engine.begin() as conn:
            # Create table if not exists
            await conn.run_sync(
                lambda sync_conn: table.create(sync_conn, checkfirst=True)
            )

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        async with self.engine.connect() as conn:
            result = await conn.run_sync(
                lambda sync_conn: sync_conn.dialect.has_table(sync_conn, table_name)
            )
            return result

    def _build_where_clause(self, table: Table, query: Query):
        """Build SQLAlchemy WHERE clause from query conditions"""
        if not query.conditions:
            return None

        clauses = []
        for condition in query.conditions:
            column = table.c[condition.field]
            op = condition.operator

            if op == ComparisonOperator.EQUALS:
                clauses.append(column == condition.value)
            elif op == ComparisonOperator.NOT_EQUALS:
                clauses.append(column != condition.value)
            elif op == ComparisonOperator.GREATER_THAN:
                clauses.append(column > condition.value)
            elif op == ComparisonOperator.GREATER_THAN_OR_EQUAL:
                clauses.append(column >= condition.value)
            elif op == ComparisonOperator.LESS_THAN:
                clauses.append(column < condition.value)
            elif op == ComparisonOperator.LESS_THAN_OR_EQUAL:
                clauses.append(column <= condition.value)
            elif op == ComparisonOperator.LIKE:
                clauses.append(column.like(condition.value))
            elif op == ComparisonOperator.IN:
                clauses.append(column.in_(condition.value))
            elif op == ComparisonOperator.NOT_IN:
                clauses.append(column.notin_(condition.value))
            elif op == ComparisonOperator.IS_NULL:
                clauses.append(column.is_(None))
            elif op == ComparisonOperator.IS_NOT_NULL:
                clauses.append(column.isnot(None))

        # Combine with AND or OR
        if query.logical_operator == LogicalOperator.AND:
            return and_(*clauses)
        else:
            return or_(*clauses)

    async def execute_query(self, query: Query) -> List[Dict[str, Any]]:
        """Execute SELECT query"""
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        entity_meta = get_entity_metadata(query.entity_type)
        table = self._get_or_create_table(entity_meta)

        # Build SELECT statement
        stmt = select(table)

        # Add WHERE clause
        where_clause = self._build_where_clause(table, query)
        if where_clause is not None:
            stmt = stmt.where(where_clause)

        # Add ORDER BY
        if query.order_by:
            column = table.c[query.order_by]
            stmt = stmt.order_by(column.desc() if query.order_desc else column.asc())

        # Add LIMIT/OFFSET
        if query.limit:
            stmt = stmt.limit(query.limit)
        if query.offset:
            stmt = stmt.offset(query.offset)

        # Execute
        async with self.engine.connect() as conn:
            result = await conn.execute(stmt)
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

    async def execute_insert(self, table: str, data: Dict[str, Any]) -> Any:
        """Execute INSERT"""
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        table_obj = self._tables.get(table)
        if table_obj is None:
            raise DataException(f"Table {table} not found in metadata")

        stmt = insert(table_obj).values(**data)

        async with self.engine.connect() as conn:
            async with conn.begin():
                result = await conn.execute(stmt)
                # Return the inserted primary key
                return (
                    result.inserted_primary_key[0]
                    if result.inserted_primary_key
                    else None
                )

    async def execute_update(
        self,
        table: str,
        primary_key_field: str,
        primary_key_value: Any,
        data: Dict[str, Any],
    ) -> None:
        """Execute UPDATE"""
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        table_obj = self._tables.get(table)
        if table_obj is None:
            raise DataException(f"Table {table} not found in metadata")

        pk_column = table_obj.c[primary_key_field]
        stmt = update(table_obj).where(pk_column == primary_key_value).values(**data)

        async with self.engine.connect() as conn:
            async with conn.begin():
                await conn.execute(stmt)

    async def execute_delete(
        self, table: str, primary_key_field: str, primary_key_value: Any
    ) -> None:
        """Execute DELETE by primary key"""
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        table_obj = self._tables.get(table)
        if table_obj is None:
            raise DataException(f"Table {table} not found in metadata")

        pk_column = table_obj.c[primary_key_field]
        stmt = delete(table_obj).where(pk_column == primary_key_value)

        async with self.engine.connect() as conn:
            async with conn.begin():
                await conn.execute(stmt)

    async def execute_delete_query(self, query: Query) -> int:
        """Execute DELETE with conditions"""
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        entity_meta = get_entity_metadata(query.entity_type)
        table = self._get_or_create_table(entity_meta)

        stmt = delete(table)

        where_clause = self._build_where_clause(table, query)
        if where_clause is not None:
            stmt = stmt.where(where_clause)

        async with self.engine.connect() as conn:
            async with conn.begin():
                result = await conn.execute(stmt)
                return result.rowcount

    async def execute_count(self, query: Query) -> int:
        """Execute COUNT query"""
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        entity_meta = get_entity_metadata(query.entity_type)
        table = self._get_or_create_table(entity_meta)

        stmt = select(func.count()).select_from(table)

        where_clause = self._build_where_clause(table, query)
        if where_clause is not None:
            stmt = stmt.where(where_clause)

        async with self.engine.connect() as conn:
            result = await conn.execute(stmt)
            return result.scalar()

    async def execute_exists(self, query: Query) -> bool:
        """Execute EXISTS query"""
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        entity_meta = get_entity_metadata(query.entity_type)
        table = self._get_or_create_table(entity_meta)

        # Build a simple SELECT 1 query with conditions
        stmt = select(1).select_from(table)

        where_clause = self._build_where_clause(table, query)
        if where_clause is not None:
            stmt = stmt.where(where_clause)

        stmt = stmt.limit(1)

        async with self.engine.connect() as conn:
            result = await conn.execute(stmt)
            return result.first() is not None

    def _parse_orm_query(
        self, query_string: str, entity_metadata: EntityMetadata
    ) -> str:
        """
        Parse ORM-style query to SQL.

        Converts queries like:
            "SELECT u FROM User u WHERE u.email = :email"
        To:
            "SELECT * FROM users WHERE email = :email"

        Also handles UPDATE and DELETE:
            "UPDATE User u SET u.active = :status"
        To:
            "UPDATE users SET active = :status"
        """
        # Try to match different query patterns
        select_pattern = r"^\s*(SELECT)\s+(\w+)\s+FROM\s+(\w+)\s+(\w+)\b"
        update_pattern = r"^\s*(UPDATE)\s+(\w+)\s+(\w+)\b"
        delete_pattern = r"^\s*(DELETE)\s+FROM\s+(\w+)\s+(\w+)\b"

        # Determine operation type and extract components
        match = re.match(select_pattern, query_string, re.IGNORECASE)
        if match:
            operation = "SELECT"
            select_alias = match.group(2)
            entity_name = match.group(3)
            alias = match.group(4)
        else:
            match = re.match(update_pattern, query_string, re.IGNORECASE)
            if match:
                operation = "UPDATE"
                entity_name = match.group(2)
                alias = match.group(3)
            else:
                match = re.match(delete_pattern, query_string, re.IGNORECASE)
                if match:
                    operation = "DELETE"
                    entity_name = match.group(2)
                    alias = match.group(3)
                else:
                    # No ORM pattern found, return as-is (probably native SQL)
                    return query_string

        # First replace all alias.field references with just field
        # e.g., u.email -> email, u.age -> age
        query = query_string
        for field_name in entity_metadata.fields.keys():
            query = re.sub(rf"\b{alias}\.{field_name}\b", field_name, query)

        # Then replace entity references with table name based on operation
        if operation == SQLOperation.SELECT:
            # Replace SELECT <alias> FROM <Entity> <alias>
            query = re.sub(
                rf"\bSELECT\s+{select_alias}\s+FROM\s+{entity_name}\s+{alias}\b",
                f"SELECT * FROM {entity_metadata.table_name}",
                query,
                flags=re.IGNORECASE,
            )
        elif operation == SQLOperation.UPDATE:
            # Replace UPDATE <Entity> <alias>
            query = re.sub(
                rf"\bUPDATE\s+{entity_name}\s+{alias}\b",
                f"UPDATE {entity_metadata.table_name}",
                query,
                flags=re.IGNORECASE,
            )
        elif operation == SQLOperation.DELETE:
            # Replace DELETE FROM <Entity> <alias>
            query = re.sub(
                rf"\bDELETE\s+FROM\s+{entity_name}\s+{alias}\b",
                f"DELETE FROM {entity_metadata.table_name}",
                query,
                flags=re.IGNORECASE,
            )

        return query

    async def execute_custom_query(
        self,
        query_string: str,
        params: dict,
        native: bool = False,
        entity_metadata: EntityMetadata = None,
    ) -> list[dict]:
        """
        Execute custom query with parameter binding.

        Args:
            query_string: SQL query string with :param placeholders
            params: Dictionary of parameter values
            native: If True, execute as raw SQL. If False, parse ORM syntax
            entity_metadata: Entity metadata for ORM query parsing

        Returns:
            List of result rows as dictionaries
        """
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        # Parse ORM query if not native
        if not native and entity_metadata:
            query_string = self._parse_orm_query(query_string, entity_metadata)

        stmt = text(query_string)

        async with self.engine.connect() as conn:
            result = await conn.execute(stmt, params)
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

    async def execute_custom_modifying_query(
        self,
        query_string: str,
        params: dict,
        native: bool = False,
        entity_metadata: EntityMetadata = None,
    ) -> int:
        """
        Execute custom UPDATE/DELETE query with parameter binding.

        Args:
            query_string: SQL query string with :param placeholders
            params: Dictionary of parameter values
            native: If True, execute as raw SQL. If False, parse ORM syntax
            entity_metadata: Entity metadata for ORM query parsing

        Returns:
            Number of affected rows
        """
        if not self.engine:
            raise DatabaseNotConnectedException("Database not connected")

        # Parse ORM query if not native
        if not native and entity_metadata:
            query_string = self._parse_orm_query(query_string, entity_metadata)

        stmt = text(query_string)

        async with self.engine.connect() as conn:
            async with conn.begin():
                result = await conn.execute(stmt, params)
                return result.rowcount
