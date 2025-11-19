from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from typing import Any, Dict, Set, Union, get_args, get_origin

# Global registry for component schemas
_schema_registry: Dict[str, Dict[str, Any]] = {}
_registered_types: Set[type] = set()


def type_to_schema(python_type: Any, use_refs: bool = True) -> Dict[str, Any]:
    """
    Convert Python type to JSON Schema.

    Supports:
    - Primitives: int, str, float, bool
    - Lists: List[T]
    - Dicts: Dict[str, T]
    - Dataclasses
    - Pydantic models (if available)
    - Optional types
    - Enums

    Args:
        python_type: Python type to convert

    Returns:
        JSON Schema dictionary
    """
    if python_type is None or python_type is type(None):
        return {"type": "null"}

    # Get origin for generic types (List, Dict, Optional, etc.)
    origin = get_origin(python_type)

    # Handle Union types (including Optional)
    if origin is Union:
        args = get_args(python_type)
        # Check if this is Optional[T] (Union[T, None])
        if type(None) in args:
            non_none_types = [a for a in args if a is not type(None)]
            if len(non_none_types) == 1:
                # Optional[T] - make schema nullable
                base_schema = type_to_schema(non_none_types[0])
                base_schema["nullable"] = True
                return base_schema
            else:
                # Union of multiple types
                return {"anyOf": [type_to_schema(arg) for arg in args]}
        else:
            # Union without None
            return {"anyOf": [type_to_schema(arg) for arg in args]}

    # Primitive types
    if python_type is int:
        return {"type": "integer"}
    if python_type is str:
        return {"type": "string"}
    if python_type is float:
        return {"type": "number"}
    if python_type is bool:
        return {"type": "boolean"}

    # List[T]
    if origin is list:
        args = get_args(python_type)
        if args:
            return {"type": "array", "items": type_to_schema(args[0])}
        return {"type": "array", "items": {}}

    # Dict[str, T]
    if origin is dict:
        args = get_args(python_type)
        if len(args) == 2:
            # Specific value type
            return {"type": "object", "additionalProperties": type_to_schema(args[1])}
        return {"type": "object", "additionalProperties": True}

    # Enum
    if isinstance(python_type, type) and issubclass(python_type, Enum):
        if use_refs:
            # Register enum and return $ref
            schema_name = python_type.__name__
            if python_type not in _registered_types:
                _schema_registry[schema_name] = enum_to_schema(python_type)
                _registered_types.add(python_type)
            return {"$ref": f"#/components/schemas/{schema_name}"}
        else:
            return enum_to_schema(python_type)

    # Dataclass
    if is_dataclass(python_type):
        if use_refs:
            # Register dataclass and return $ref
            schema_name = python_type.__name__
            if python_type not in _registered_types:
                _schema_registry[schema_name] = dataclass_to_schema(
                    python_type, use_refs=use_refs
                )
                _registered_types.add(python_type)
            return {"$ref": f"#/components/schemas/{schema_name}"}
        else:
            return dataclass_to_schema(python_type, use_refs=use_refs)

    # Pydantic model (optional support)
    if hasattr(python_type, "model_json_schema"):
        try:
            return python_type.model_json_schema()
        except Exception:
            pass

    # Fallback for unknown types
    return {"type": "object"}


def dataclass_to_schema(dc_class, use_refs: bool = True) -> Dict[str, Any]:
    """
    Convert dataclass to JSON Schema.

    Args:
        dc_class: Dataclass type
        use_refs: Whether to use $ref for nested types

    Returns:
        JSON Schema dictionary with properties and required fields
    """
    properties = {}
    required = []

    for field in fields(dc_class):
        # Convert field type to schema (use $ref for nested types)
        properties[field.name] = type_to_schema(field.type, use_refs=use_refs)

        # Add description if available from field metadata
        if field.metadata and "description" in field.metadata:
            properties[field.name]["description"] = field.metadata["description"]

        # Check if field is required (no default value)
        if field.default is MISSING and field.default_factory is MISSING:
            required.append(field.name)

    schema = {
        "type": "object",
        "properties": properties,
    }

    if required:
        schema["required"] = required

    # Add title from class name
    schema["title"] = dc_class.__name__

    return schema


def enum_to_schema(enum_class) -> Dict[str, Any]:
    """
    Convert Enum to JSON Schema.

    Args:
        enum_class: Enum type

    Returns:
        JSON Schema dictionary with enum values
    """
    # Get enum values
    values = [e.value for e in enum_class]

    # Determine type from first value
    if values:
        first_value = values[0]
        if isinstance(first_value, str):
            schema_type = "string"
        elif isinstance(first_value, int):
            schema_type = "integer"
        elif isinstance(first_value, float):
            schema_type = "number"
        else:
            schema_type = "string"
    else:
        schema_type = "string"

    return {"type": schema_type, "enum": values, "title": enum_class.__name__}


def get_schema_registry() -> Dict[str, Dict[str, Any]]:
    """
    Get the current schema registry.

    Returns:
        Dictionary of schema name to schema definition
    """
    return _schema_registry.copy()


def clear_schema_registry():
    """Clear the schema registry. Useful for testing or regenerating schemas."""
    global _schema_registry, _registered_types
    _schema_registry = {}
    _registered_types = set()
