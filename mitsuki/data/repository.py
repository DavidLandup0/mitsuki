import ast
import inspect
import re
import textwrap
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, List, Optional, Type, get_args, get_origin

from mitsuki.core.container import get_container
from mitsuki.core.enums import Scope
from mitsuki.core.logging import get_logger
from mitsuki.core.utils import uuid7
from mitsuki.data.entity import get_entity_metadata, is_entity
from mitsuki.data.query import ComparisonOperator, Query, QueryOperation
from mitsuki.data.query_parser import parse_query_method
from mitsuki.data.types import _IdMarker, _UUIDMarker
from mitsuki.exceptions import (
    DataException,
    EntityException,
    QueryException,
    UUIDGenerationException,
)

# Global adapter instance (will be set during application startup)
_database_adapter = None


def set_database_adapter(adapter):
    """Set the global database adapter instance"""
    global _database_adapter
    _database_adapter = adapter


def get_database_adapter():
    """Get the global database adapter instance"""
    if _database_adapter is None:
        raise DataException(
            "Database adapter not initialized. Did you start the application?"
        )
    return _database_adapter


class CrudRepositoryProxy:
    """
    Proxy class that implements repository methods dynamically.
    Handles both base CRUD operations and query DSL methods.
    """

    def __init__(self, entity_type: Type, adapter):
        self.entity_type = entity_type
        self.adapter = adapter
        self.entity_metadata = get_entity_metadata(entity_type)

    def get_connection(self):
        """
        Get a database connection context manager for custom queries.
        Connection is automatically closed when exiting the context.

        Returns:
            AsyncConnection context manager

        Example:
            async def custom_complex_query(self):
                adapter = get_database_adapter()
                user_table = adapter.get_table(User)

                async with self.get_connection() as conn:
                    query = select(user_table).where(user_table.c.active == True)
                    result = await conn.execute(query)
                    rows = result.fetchall()
                    return [dict(row._mapping) for row in rows]
        """
        return self.adapter.get_connection()

    def _entity_to_dict(self, entity: Any) -> dict:
        """Convert entity instance to dictionary"""
        if hasattr(entity, "__dataclass_fields__"):
            return asdict(entity)
        elif hasattr(entity, "__dict__"):
            return entity.__dict__
        else:
            raise EntityException(f"Cannot convert {type(entity)} to dict")

    def _dict_to_entity(self, data: dict) -> Any:
        """Convert dictionary to entity instance"""
        # For UUID fields, ensure they're UUID objects
        # PostgreSQL with native UUID: already UUID objects
        # SQLite/MySQL with String: need conversion from string
        pk_field = self.entity_metadata.primary_key_field
        pk_field_meta = self.entity_metadata.get_primary_key()

        if pk_field_meta.uuid_version is not None and pk_field in data:
            # If it's a string, convert to UUID object
            if isinstance(data[pk_field], str):
                data[pk_field] = uuid.UUID(data[pk_field])
            # If it's already a UUID object (PostgreSQL), leave it as is

        # Convert datetime strings to datetime objects
        for field_name, field_meta in self.entity_metadata.fields.items():
            if field_name in data and data[field_name] is not None:
                # Get the actual type, unwrapping Optional if needed
                python_type = field_meta.python_type
                origin = get_origin(python_type)
                if origin is not None:
                    # Handle Optional[T] -> get T
                    args = get_args(python_type)
                    if args:
                        python_type = args[0]

                # Check if field is datetime type
                if python_type == datetime:
                    if isinstance(data[field_name], str):
                        # Parse ISO format datetime string
                        data[field_name] = datetime.fromisoformat(data[field_name])

        return self.entity_type(**data)

    def _generate_uuid(self, version: int, namespace: Any = None) -> uuid.UUID:
        """Generate UUID based on version"""
        if version == 1:
            return uuid.uuid1()
        elif version == 4:
            return uuid.uuid4()
        elif version == 5:
            if namespace is None:
                raise UUIDGenerationException("UUID v5 requires a namespace")
            return uuid.uuid5(namespace, self.entity_type.__name__)
        elif version == 7:
            return uuid7()
        else:
            raise UUIDGenerationException(f"Unsupported UUID version: {version}")

    async def save(self, entity: Any) -> Any:
        """Insert new or update existing entity"""
        pk_field = self.entity_metadata.primary_key_field
        pk_value = getattr(entity, pk_field)
        pk_field_meta = self.entity_metadata.get_primary_key()

        entity_dict = self._entity_to_dict(entity)

        # Update update_on_save timestamp fields
        for field_name, field_meta in self.entity_metadata.fields.items():
            if field_meta.update_on_save:
                entity_dict[field_name] = datetime.now()
                setattr(entity, field_name, entity_dict[field_name])

        # Check if insert or update
        # New entity if: pk is None, 0, empty string, or a marker object
        is_new = (
            pk_value is None
            or pk_value == 0
            or pk_value == ""
            or isinstance(pk_value, (_IdMarker, _UUIDMarker))
        )

        if is_new:
            # Generate UUID if this is a UUID field
            if pk_field_meta.uuid_version is not None:
                generated_uuid = self._generate_uuid(
                    pk_field_meta.uuid_version, pk_field_meta.uuid_namespace
                )
                setattr(
                    entity, pk_field, generated_uuid
                )  # Keep as UUID object in entity
                # SQLAlchemy will handle UUID conversion based on dialect
                # PostgreSQL: stores as native UUID
                # SQLite/MySQL: stores as string
                entity_dict[pk_field] = generated_uuid
                pk_value = generated_uuid

            # INSERT
            # Set update_on_create fields
            for field_name, field_meta in self.entity_metadata.fields.items():
                if field_meta.update_on_create:
                    entity_dict[field_name] = datetime.now()
                    setattr(entity, field_name, entity_dict[field_name])

            # Remove auto-increment primary key from insert data
            insertable_fields = self.entity_metadata.get_insertable_fields()
            insert_data = {
                k: v for k, v in entity_dict.items() if k in insertable_fields
            }

            # Execute insert
            inserted_pk = await self.adapter.execute_insert(
                self.entity_metadata.table_name, insert_data
            )

            # Update entity with new primary key
            if inserted_pk is not None:
                setattr(entity, pk_field, inserted_pk)

            return entity
        else:
            # UPDATE
            updatable_fields = self.entity_metadata.get_updatable_fields()
            update_data = {
                k: v for k, v in entity_dict.items() if k in updatable_fields
            }

            await self.adapter.execute_update(
                self.entity_metadata.table_name, pk_field, pk_value, update_data
            )
            return entity

    async def find_by_id(self, id: Any) -> Optional[Any]:
        """Find entity by primary key"""
        pk_field = self.entity_metadata.primary_key_field

        query = Query(entity_type=self.entity_type, operation=QueryOperation.SELECT)
        query.add_condition(pk_field, ComparisonOperator.EQUALS, id)

        results = await self.adapter.execute_query(query)
        if results:
            return self._dict_to_entity(results[0])
        return None

    async def find_all(
        self,
        page: Optional[int] = None,
        size: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
    ) -> List[Any]:
        """
        Get all entities with optional pagination and sorting.

        Args:
            page: Page number (0-indexed), None for no pagination
            size: Page size, None for no pagination
            sort_by: Field name to sort by
            sort_desc: Sort in descending order
        """
        query = Query(entity_type=self.entity_type, operation=QueryOperation.SELECT)

        # Add pagination
        if page is not None and size is not None:
            query.offset = page * size
            query.limit = size

        # Add sorting
        if sort_by:
            query.order_by = sort_by
            query.order_desc = sort_desc

        results = await self.adapter.execute_query(query)
        return [self._dict_to_entity(row) for row in results]

    async def delete(self, entity: Any) -> bool:
        """Delete entity"""
        pk_field = self.entity_metadata.primary_key_field
        pk_value = getattr(entity, pk_field)
        return await self.delete_by_id(pk_value)

    async def delete_by_id(self, id: Any) -> bool:
        """Delete entity by primary key"""
        pk_field = self.entity_metadata.primary_key_field

        await self.adapter.execute_delete(self.entity_metadata.table_name, pk_field, id)
        return True

    async def exists_by_id(self, id: Any) -> bool:
        """Check if entity exists by primary key"""
        pk_field = self.entity_metadata.primary_key_field

        query = Query(entity_type=self.entity_type, operation=QueryOperation.EXISTS)
        query.add_condition(pk_field, ComparisonOperator.EQUALS, id)

        return await self.adapter.execute_exists(query)

    async def count(self) -> int:
        """Count all entities"""
        query = Query(entity_type=self.entity_type, operation=QueryOperation.COUNT)

        return await self.adapter.execute_count(query)

    def _handle_query_dsl_method(self, method_name: str, args: tuple) -> Any:
        """
        Handle query DSL methods like find_by_email, count_by_status, etc.
        This is called dynamically when a query DSL method is invoked.
        """
        try:
            # Parse method name into Query object
            query = parse_query_method(method_name, self.entity_type, args)

            # Execute based on operation type
            if query.operation == QueryOperation.SELECT:
                return self._execute_select_query(query)
            elif query.operation == QueryOperation.COUNT:
                return self._execute_count_query(query)
            elif query.operation == QueryOperation.DELETE:
                return self._execute_delete_query(query)
            elif query.operation == QueryOperation.EXISTS:
                return self._execute_exists_query(query)
            else:
                raise QueryException(f"Unsupported operation: {query.operation}")

        except QueryException as e:
            raise QueryException(f"Cannot parse method '{method_name}': {e}")

    async def _execute_select_query(self, query: Query) -> Any:
        """Execute SELECT query and return results as list"""
        results = await self.adapter.execute_query(query)

        # Convert to entity instances
        entities = [self._dict_to_entity(row) for row in results]

        # Always return list for find_by methods
        # Individual repos can customize if they want single results
        return entities

    async def _execute_count_query(self, query: Query) -> int:
        """Execute COUNT query"""
        return await self.adapter.execute_count(query)

    async def _execute_delete_query(self, query: Query) -> None:
        """Execute DELETE query"""
        await self.adapter.execute_delete_query(query)

    async def _execute_exists_query(self, query: Query) -> bool:
        """Execute EXISTS query"""
        return await self.adapter.execute_exists(query)

    def _is_modifying_query(self, query_string: str) -> bool:
        """
        Detect if a query is modifying (UPDATE/DELETE/INSERT).

        Returns:
            True if query modifies data, False otherwise
        """
        operation_pattern = r"^\s*(UPDATE|DELETE|INSERT)\b"
        match = re.match(operation_pattern, query_string, re.IGNORECASE)
        return match is not None

    async def _handle_custom_query(self, method: Any, args: tuple, kwargs: dict) -> Any:
        """
        Handle @Query decorated methods.
        Parses the query string, binds parameters, and executes.
        """
        logger = get_logger()

        # Get query metadata from decorator - fields are always present
        query_string = method.__mitsuki_query_string__
        is_native = method.__mitsuki_query_native__
        is_modifying = method.__mitsuki_query_modifying__

        # Validate: modifying queries must have @Modifying decorator
        if self._is_modifying_query(query_string) and not is_modifying:
            raise QueryException(
                f"Query contains modifying operation (UPDATE/DELETE/INSERT) but is missing @Modifying decorator. "
                f"Add @Modifying decorator to method '{method.__name__}'"
            )

        # Get method signature to map parameters
        sig = inspect.signature(method)
        param_names = list(sig.parameters.keys())[1:]  # Skip 'self'

        # Build parameter dictionary from args and kwargs
        params = {}
        for i, value in enumerate(args):
            if i < len(param_names):
                params[param_names[i]] = value

        params.update(kwargs)

        # Check if query uses positional parameters (?1, ?2, etc.)
        # If so, convert to named parameters for SQLAlchemy
        if "?" in query_string and ":" not in query_string:
            # Convert positional to named parameters
            # ?1, ?2, ?3 -> :param_0, :param_1, :param_2
            # Use param_names to get values in order from params dict
            positional_params = {}
            for i, param_name in enumerate(param_names):
                if param_name not in ("limit", "offset") and param_name in params:
                    positional_params[f"param_{i}"] = params[param_name]

            # Replace ?1 with :param_0, ?2 with :param_1, etc.
            for i in range(len(positional_params)):
                query_string = query_string.replace(f"?{i + 1}", f":param_{i}")

            # Keep limit/offset in params for pagination handling below
            limit_val = params.get("limit")
            offset_val = params.get("offset")
            params = positional_params
            if limit_val is not None:
                params["limit"] = limit_val
            if offset_val is not None:
                params["offset"] = offset_val

        # Handle pagination parameters (limit, offset)
        # Extract them from params and add to query if present
        limit = params.pop("limit", None)
        offset = params.pop("offset", None)

        if limit is not None or offset is not None:
            # Validate pagination parameters
            if limit is not None:
                try:
                    limit_int = int(limit)
                    if limit_int < 0:
                        raise QueryException("LIMIT must be non-negative")
                    query_string = f"{query_string.rstrip()} LIMIT {limit_int}"
                except (ValueError, TypeError) as e:
                    raise QueryException(f"Invalid LIMIT parameter: {e}")

            if offset is not None:
                try:
                    offset_int = int(offset)
                    if offset_int < 0:
                        raise QueryException("OFFSET must be non-negative")
                    query_string = f"{query_string.rstrip()} OFFSET {offset_int}"
                except (ValueError, TypeError) as e:
                    raise QueryException(f"Invalid OFFSET parameter: {e}")

        # Log the query
        logger.debug(f"Executing {'native' if is_native else 'ORM'} query:")
        logger.debug(query_string)
        logger.debug(f"Parameters: {params}")

        # Execute query through adapter
        if is_modifying:
            # Execute modifying query (UPDATE/DELETE)
            affected_rows = await self.adapter.execute_custom_modifying_query(
                query_string,
                params,
                native=is_native,
                entity_metadata=self.entity_metadata,
            )
            return affected_rows
        else:
            # Execute select query
            results = await self.adapter.execute_custom_query(
                query_string,
                params,
                native=is_native,
                entity_metadata=self.entity_metadata,
            )

            # Convert results to entity instances
            if results:
                return [self._dict_to_entity(row) for row in results]
            return []


def CrudRepository(entity: Type):
    """
    Decorator that auto-generates repository implementation.

    The decorated class should be an interface (class with method stubs).
    The decorator will:
    1. Generate implementations for base CRUD methods (save, find_by_id, etc.)
    2. Parse and implement query DSL methods (find_by_*, count_by_*, etc.)
    3. Register the repository in the DI container

    Args:
        entity: The entity type this repository manages

    Example:
        @CrudRepository(entity=User)
        class UserRepository:
            async def find_by_email(self, email: str) -> Optional[User]: ...
            async def find_by_age_greater_than(self, age: int) -> List[User]: ...

    The framework will auto-implement all methods!
    """
    if not is_entity(entity):
        raise ValueError(
            f"{entity.__name__} is not an @Entity. Did you forget the @Entity decorator?"
        )

    def decorator(repo_class: Type) -> Type:
        # Get database adapter
        adapter = get_database_adapter

        # Create a new class that wraps the proxy
        class GeneratedRepository:
            def __init__(self):
                # Lazy-initialize adapter (may not be available at decoration time)
                self._proxy = None

            def _get_proxy(self):
                if self._proxy is None:
                    self._proxy = CrudRepositoryProxy(entity, adapter())
                return self._proxy

            def __getattribute__(self, name):
                # Handle special attributes
                if name.startswith("_"):
                    return object.__getattribute__(self, name)

                proxy = self._get_proxy()

                # Check if it's a base CRUD method
                if hasattr(proxy, name):
                    return getattr(proxy, name)

                # Check if it's defined in the original repo class
                if hasattr(repo_class, name):
                    original_method = getattr(repo_class, name)

                    # Check if it's a @Query decorated method
                    if callable(original_method) and hasattr(
                        original_method, "__mitsuki_query__"
                    ):
                        # Create wrapper that calls the proxy's custom query handler
                        async def custom_query_wrapper(*args, **kwargs):
                            return await proxy._handle_custom_query(
                                original_method, args, kwargs
                            )

                        return custom_query_wrapper

                    # Check if it's a real implementation (not just a stub with ... or pass)
                    if callable(original_method):
                        source = inspect.getsource(original_method)
                        # Remove leading indentation
                        source = textwrap.dedent(source)

                        # Parse the method to check if it's a stub
                        # A stub is a method that only contains 'pass' or '...' (Ellipsis)
                        is_stub = False
                        try:
                            tree = ast.parse(source)
                            # Get the function definition
                            func_def = tree.body[0]
                            if isinstance(
                                func_def, (ast.FunctionDef, ast.AsyncFunctionDef)
                            ):
                                # Check if body only contains Pass or Expr(Ellipsis)
                                if len(func_def.body) == 1:
                                    stmt = func_def.body[0]
                                    if isinstance(stmt, ast.Pass):
                                        is_stub = True
                                    elif isinstance(stmt, ast.Expr) and isinstance(
                                        stmt.value, ast.Constant
                                    ):
                                        # Check for ellipsis (...)
                                        if stmt.value.value is Ellipsis:
                                            is_stub = True
                        except Exception:
                            # If we can't parse it, assume it's not a stub
                            pass

                        if is_stub:
                            # Query DSL method (has annotations but no implementation)
                            async def query_dsl_wrapper(*args, **kwargs):
                                return await proxy._handle_query_dsl_method(name, args)

                            return query_dsl_wrapper
                        else:
                            # Real implementation - bind to proxy
                            bound_method = original_method.__get__(proxy, type(proxy))
                            return bound_method

                raise QueryException(
                    f"'{repo_class.__name__}' object has no attribute '{name}'"
                )

        # Copy class name and metadata
        GeneratedRepository.__name__ = repo_class.__name__
        GeneratedRepository.__qualname__ = repo_class.__qualname__
        GeneratedRepository.__module__ = repo_class.__module__

        # Mark as repository
        GeneratedRepository.__mitsuki_repository__ = True
        GeneratedRepository.__mitsuki_entity_type__ = entity

        # Register in DI container
        container = get_container()
        container.register(
            GeneratedRepository, name=repo_class.__name__, scope=Scope.SINGLETON
        )

        return GeneratedRepository

    return decorator
