"""
Abstract database adapter interface.
Defines the contract that all database adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from mitsuki.data.query import Query


class DatabaseAdapter(ABC):
    """
    Abstract base class for database adapters.
    Implementations provide actual database connectivity (SQLAlchemy, raw SQL, etc.)
    """

    @abstractmethod
    async def connect(self, connection_string: str) -> None:
        """
        Establish connection to the database.

        Args:
            connection_string: Database connection string (e.g., postgresql://...)
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection and cleanup resources."""
        pass

    @abstractmethod
    async def execute_query(self, query: Query) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries.

        Args:
            query: Query object representing the SELECT operation

        Returns:
            List of dictionaries, one per row
        """
        pass

    @abstractmethod
    async def execute_insert(self, table: str, data: Dict[str, Any]) -> Any:
        """
        Execute an INSERT statement.

        Args:
            table: Table name
            data: Dictionary of column_name -> value

        Returns:
            The primary key value of the inserted row
        """
        pass

    @abstractmethod
    async def execute_update(
        self,
        table: str,
        primary_key_field: str,
        primary_key_value: Any,
        data: Dict[str, Any],
    ) -> None:
        """
        Execute an UPDATE statement.

        Args:
            table: Table name
            primary_key_field: Name of the primary key column
            primary_key_value: Value of the primary key to update
            data: Dictionary of column_name -> value to update
        """
        pass

    @abstractmethod
    async def execute_delete(
        self, table: str, primary_key_field: str, primary_key_value: Any
    ) -> None:
        """
        Execute a DELETE statement by primary key.

        Args:
            table: Table name
            primary_key_field: Name of the primary key column
            primary_key_value: Value of the primary key to delete
        """
        pass

    @abstractmethod
    async def execute_delete_query(self, query: Query) -> int:
        """
        Execute a DELETE statement with conditions.

        Args:
            query: Query object with DELETE operation and conditions

        Returns:
            Number of rows deleted
        """
        pass

    @abstractmethod
    async def execute_count(self, query: Query) -> int:
        """
        Execute a COUNT query.

        Args:
            query: Query object with COUNT operation

        Returns:
            Count of matching rows
        """
        pass

    @abstractmethod
    async def execute_exists(self, query: Query) -> bool:
        """
        Execute an EXISTS query.

        Args:
            query: Query object with EXISTS operation

        Returns:
            True if at least one row matches, False otherwise
        """
        pass

    @abstractmethod
    async def create_table_if_not_exists(self, entity_metadata) -> None:
        """
        Create table for an entity if it doesn't exist.

        Args:
            entity_metadata: EntityMetadata object describing the table structure
        """
        pass

    @abstractmethod
    async def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """
        pass
