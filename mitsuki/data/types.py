import typing
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Optional, Type

from mitsuki.exceptions import UUIDGenerationException

SUPPORTED_UUID_VERSIONS = [1, 4, 5, 7]


@dataclass
class FieldMetadata:
    """
    Metadata about an entity field.
    Stores information needed for ORM mapping.
    """

    name: str
    python_type: Type
    db_type: Optional[str] = None
    nullable: bool = True
    unique: bool = False
    index: bool = False
    max_length: Optional[int] = None
    default: Any = None
    primary_key: bool = False
    auto_increment: bool = False
    update_on_create: bool = False  # Set timestamp on creation
    update_on_save: bool = False  # Update timestamp on modification
    uuid_version: Optional[int] = None  # UUID version if this is a UUID field
    uuid_namespace: Optional[Any] = None  # UUID namespace for v5


@dataclass
class EntityMetadata:
    """
    Metadata about an entity class.
    Stores table mapping and field information.
    """

    entity_class: Type
    table_name: str
    fields: dict[str, FieldMetadata] = field(default_factory=dict)
    primary_key_field: Optional[str] = None

    def get_primary_key(self) -> FieldMetadata:
        """Get the primary key field metadata"""
        if not self.primary_key_field:
            raise UUIDGenerationException(
                f"Entity {self.entity_class.__name__} has no primary key defined"
            )
        return self.fields[self.primary_key_field]

    def get_field(self, name: str) -> FieldMetadata:
        """Get field metadata by name"""
        if name not in self.fields:
            raise UUIDGenerationException(
                f"Field '{name}' not found in entity {self.entity_class.__name__}"
            )
        return self.fields[name]

    def get_insertable_fields(self) -> dict[str, FieldMetadata]:
        """Get fields that should be included in INSERT statements (excludes auto-increment PKs)"""
        return {
            name: field_meta
            for name, field_meta in self.fields.items()
            if not (field_meta.primary_key and field_meta.auto_increment)
        }

    def get_updatable_fields(self) -> dict[str, FieldMetadata]:
        """Get fields that can be updated (excludes primary key and update_on_create fields)"""
        return {
            name: field_meta
            for name, field_meta in self.fields.items()
            if not field_meta.primary_key and not field_meta.update_on_create
        }


class _IdMarker:
    """
    Marker class for primary key fields.
    Usage: id: int = Id()
    """

    def __init__(self, auto_increment: bool = True):
        self.auto_increment = auto_increment
        self.primary_key = True


class _UUIDMarker:
    """
    Marker class for UUID primary key fields.
    Usage: id: uuid.UUID = UUID() or id: uuid.UUID = UUIDv4()
    """

    def __init__(self, version: int = 4, namespace: Any = None):
        self.version = version
        self.namespace = namespace
        self.auto_increment = False  # UUIDs are not auto-incremented
        self.primary_key = True

        # Validate version
        if version not in SUPPORTED_UUID_VERSIONS:
            raise UUIDGenerationException(
                f"UUID version {version} not supported. Use one of {SUPPORTED_UUID_VERSIONS}."
            )

        # v5 requires namespace
        if version == 5 and namespace is None:
            raise UUIDGenerationException("UUID v5 requires a namespace parameter")


class _ColumnMarker:
    """
    Marker class for column-level metadata.
    Usage: email: str = Column(unique=True, index=True, max_length=100)
    """

    def __init__(
        self,
        unique: bool = False,
        nullable: bool = True,
        index: bool = False,
        max_length: Optional[int] = None,
        default: Any = None,
        db_type: Optional[str] = None,
    ):
        self.unique = unique
        self.nullable = nullable
        self.index = index
        self.max_length = max_length
        self.default = default
        self.db_type = db_type


class _AutoTimestampMarker:
    """
    Marker for auto-timestamp fields.
    Usage: created_at: datetime = Field(update_on_create=True)
    """

    def __init__(self, update_on_create: bool = False, update_on_save: bool = False):
        self.update_on_create = update_on_create
        self.update_on_save = update_on_save


def Id(auto_increment: bool = True) -> Any:
    """
    Mark a field as the primary key.

    Args:
        auto_increment: Whether the database should auto-increment this field

    Example:
        @Entity()
        class User:
            id: int = Id()
    """
    return _IdMarker(auto_increment=auto_increment)


def Column(
    unique: bool = False,
    nullable: bool = True,
    index: bool = False,
    max_length: Optional[int] = None,
    default: Any = None,
    db_type: Optional[str] = None,
) -> Any:
    """
    Define column-level constraints and metadata.

    Args:
        unique: Whether this column should have a unique constraint
        nullable: Whether this column can be NULL
        index: Whether this column should have an index (for faster lookups)
        max_length: Maximum length for string fields (e.g., 100 for VARCHAR(100))
        default: Default value for this column
        db_type: Override the database type (e.g., "VARCHAR(255)")

    Example:
        @Entity()
        class User:
            email: str = Column(unique=True, nullable=False, max_length=100)
            username: str = Column(index=True, max_length=50)  # Indexed with max length
    """
    return _ColumnMarker(
        unique=unique,
        nullable=nullable,
        index=index,
        max_length=max_length,
        default=default,
        db_type=db_type,
    )


def Field(update_on_create: bool = False, update_on_save: bool = False) -> Any:
    """
    Define special field behavior (timestamps, etc.).

    Args:
        update_on_create: Automatically set to current timestamp on creation
        update_on_save: Automatically update to current timestamp on modification

    Example:
        @Entity()
        class User:
            created_at: datetime = Field(update_on_create=True)
            updated_at: datetime = Field(update_on_save=True)
    """
    return _AutoTimestampMarker(
        update_on_create=update_on_create, update_on_save=update_on_save
    )


def UUID(version: int = 4, namespace: Any = None) -> Any:
    """
    Mark a field as a UUID primary key.

    Args:
        version: UUID version (1, 4, 5, or 7)
        namespace: Namespace for v5 UUIDs (required for v5)

    Example:
        import uuid

        @Entity()
        class User:
            id: uuid.UUID = UUID()  # v4 by default

        @Entity()
        class Product:
            id: uuid.UUID = UUID(version=7)  # Time-ordered

        @Entity()
        class Resource:
            id: uuid.UUID = UUID(version=5, namespace=uuid.NAMESPACE_DNS)
    """
    return _UUIDMarker(version=version, namespace=namespace)


def UUIDv1() -> Any:
    """
    Mark a field as a UUID v1 primary key (timestamp + MAC address).

    Example:
        @Entity()
        class User:
            id: uuid.UUID = UUIDv1()
    """
    return _UUIDMarker(version=1)


def UUIDv4() -> Any:
    """
    Mark a field as a UUID v4 primary key (random).
    This is the default and most common UUID version.

    Example:
        @Entity()
        class User:
            id: uuid.UUID = UUIDv4()
    """
    return _UUIDMarker(version=4)


def UUIDv5(namespace: Any) -> Any:
    """
    Mark a field as a UUID v5 primary key (namespace + name hashing with SHA-1).

    Args:
        namespace: UUID namespace (e.g., uuid.NAMESPACE_DNS, uuid.NAMESPACE_URL)

    Example:
        import uuid

        @Entity()
        class Resource:
            id: uuid.UUID = UUIDv5(namespace=uuid.NAMESPACE_DNS)
    """
    return _UUIDMarker(version=5, namespace=namespace)


def UUIDv7() -> Any:
    """
    Mark a field as a UUID v7 primary key (time-ordered).
    Best for database performance with time locality.

    Example:
        @Entity()
        class Event:
            id: uuid.UUID = UUIDv7()
    """
    return _UUIDMarker(version=7)


# Python type to SQL type mapping
PYTHON_TO_SQL_TYPE_MAP = {
    int: "INTEGER",
    str: "VARCHAR(255)",
    float: "FLOAT",
    bool: "BOOLEAN",
    bytes: "BLOB",
}


def python_type_to_sql(python_type: Type) -> str:
    """
    Convert Python type to SQL type string.

    Args:
        python_type: Python type annotation

    Returns:
        SQL type string (e.g., "INTEGER", "VARCHAR(255)")
    """
    # Handle Optional types
    if hasattr(typing, "get_origin") and typing.get_origin(python_type) is typing.Union:
        args = typing.get_args(python_type)
        # Optional[X] is Union[X, None]
        non_none_types = [arg for arg in args if arg is not type(None)]
        if non_none_types:
            python_type = non_none_types[0]

    # Handle datetime specially
    if python_type == datetime:
        return "TIMESTAMP"
    elif python_type == date:
        return "DATE"
    elif python_type == time:
        return "TIME"

    # Use mapping
    return PYTHON_TO_SQL_TYPE_MAP.get(python_type, "TEXT")
