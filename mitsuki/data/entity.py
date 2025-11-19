from dataclasses import fields, is_dataclass
from typing import Optional, Type, get_type_hints

from mitsuki.data.types import (
    EntityMetadata,
    FieldMetadata,
    _AutoTimestampMarker,
    _ColumnMarker,
    _IdMarker,
    _UUIDMarker,
    python_type_to_sql,
)
from mitsuki.exceptions import EntityException

# Global registry of entity metadata
_entity_registry: dict[Type, EntityMetadata] = {}


def _pluralize(word: str) -> str:
    """
    Simple pluralization for table names.
    User -> users, Post -> posts, etc.
    TODO: Formalize this.
    """
    if word.endswith("y"):
        return word[:-1] + "ies"
    elif word.endswith("s"):
        return word + "es"
    else:
        return word + "s"


def _snake_case(name: str) -> str:
    """
    Convert CamelCase to snake_case.
    UserProfile -> user_profile
    """
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def Entity(table: Optional[str] = None):
    """
    Decorator to mark a dataclass as a database entity.

    Extracts metadata from the dataclass and registers it in the entity registry.
    Table name is auto-generated from class name (pluralized and snake_cased) if not provided.

    Args:
        table: Optional explicit table name. If not provided, infers from class name.

    Example:
        @Entity()
        @dataclass
        class User:
            id: int = Id()
            name: str
            email: str = Column(unique=True)

        @Entity(table="custom_users")
        @dataclass
        class User:
            id: int = Id()
    """

    def decorator(cls: Type) -> Type:
        # Ensure it's a dataclass
        if not is_dataclass(cls):
            raise EntityException(
                f"@Entity can only be applied to dataclasses. {cls.__name__} is not a dataclass."
            )

        # Determine table name
        table_name = table
        if not table_name:
            # Convert class name to snake_case and pluralize
            snake_name = _snake_case(cls.__name__)
            table_name = _pluralize(snake_name)

        # Create entity metadata
        entity_meta = EntityMetadata(entity_class=cls, table_name=table_name)

        # Extract field metadata from dataclass fields
        type_hints = get_type_hints(cls)
        dataclass_fields = fields(cls)

        for dc_field in dataclass_fields:
            field_name = dc_field.name
            field_type = type_hints.get(field_name, type(None))

            # Create field metadata
            field_meta = FieldMetadata(
                name=field_name,
                python_type=field_type,
                db_type=python_type_to_sql(field_type),
            )

            # Check if field has special markers
            default_value = dc_field.default
            if default_value is not None and not isinstance(default_value, type):
                # Check for Id marker
                if isinstance(default_value, _IdMarker):
                    field_meta.primary_key = True
                    field_meta.auto_increment = default_value.auto_increment
                    field_meta.nullable = False
                    entity_meta.primary_key_field = field_name

                # Check for UUID marker
                elif isinstance(default_value, _UUIDMarker):
                    field_meta.primary_key = True
                    field_meta.auto_increment = False  # UUIDs are not auto-incremented
                    field_meta.nullable = False
                    field_meta.db_type = "UUID"  # Special marker - adapter will use native type if supported
                    # Store UUID version and namespace in field metadata
                    field_meta.uuid_version = default_value.version
                    field_meta.uuid_namespace = default_value.namespace
                    entity_meta.primary_key_field = field_name

                # Check for Column marker
                elif isinstance(default_value, _ColumnMarker):
                    field_meta.unique = default_value.unique
                    field_meta.nullable = default_value.nullable
                    field_meta.index = default_value.index
                    field_meta.max_length = default_value.max_length
                    field_meta.default = default_value.default
                    if default_value.db_type:
                        field_meta.db_type = default_value.db_type

                # Check for AutoTimestamp marker
                elif isinstance(default_value, _AutoTimestampMarker):
                    field_meta.update_on_create = default_value.update_on_create
                    field_meta.update_on_save = default_value.update_on_save

            # Check default_factory for markers
            if dc_field.default_factory is not None:
                # Could be a timestamp factory like datetime.now
                pass

            # Add field to entity metadata
            entity_meta.fields[field_name] = field_meta

        # If no primary key was explicitly marked, look for 'id' field
        if not entity_meta.primary_key_field:
            if "id" in entity_meta.fields:
                entity_meta.fields["id"].primary_key = True
                entity_meta.fields["id"].auto_increment = True
                entity_meta.primary_key_field = "id"
            else:
                raise EntityException(
                    f"Entity {cls.__name__} must have a primary key. "
                    f"Either mark a field with Id() or include a field named 'id'."
                )

        # Register entity metadata
        _entity_registry[cls] = entity_meta

        # Store metadata on class for introspection
        cls.__mitsuki_entity__ = True
        cls.__mitsuki_entity_metadata__ = entity_meta

        return cls

    return decorator


def get_entity_metadata(entity_class: Type) -> EntityMetadata:
    """
    Get entity metadata for a registered entity class.

    Args:
        entity_class: The entity class

    Returns:
        EntityMetadata for the entity

    Raises:
        ValueError: If entity is not registered
    """
    if entity_class not in _entity_registry:
        raise EntityException(
            f"Entity {entity_class.__name__} is not registered. Did you forget @Entity decorator?"
        )
    return _entity_registry[entity_class]


def get_all_entities() -> dict[Type, EntityMetadata]:
    """
    Get all registered entities.

    Returns:
        Dictionary mapping entity classes to their metadata
    """
    return _entity_registry.copy()


def is_entity(cls: Type) -> bool:
    """
    Check if a class is a registered entity.

    Args:
        cls: The class to check

    Returns:
        True if the class is a registered entity
    """
    return cls in _entity_registry


def clear_entity_registry():
    """Clear the entity registry (mainly for testing)."""
    global _entity_registry
    _entity_registry.clear()
