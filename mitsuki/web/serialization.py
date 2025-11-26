import base64
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Type
from uuid import UUID

import orjson

from mitsuki.core.container import get_container

logger = logging.getLogger(__name__)

# Registry for custom type serializers
_custom_serializers: Dict[Type, Callable[[Any], Any]] = {}
_serializers_loaded = False


# Built-in type handlers
def _serialize_datetime(obj: datetime) -> str:
    return obj.isoformat()


def _serialize_date(obj: date) -> str:
    return obj.isoformat()


def _serialize_time(obj: time) -> str:
    return obj.isoformat()


def _serialize_uuid(obj: UUID) -> str:
    return str(obj)


def _serialize_decimal(obj: Decimal) -> float:
    return float(obj)


def _serialize_enum(obj: Enum) -> Any:
    return obj.value


def _serialize_dataclass(obj: Any) -> dict:
    return asdict(obj)


def _serialize_bytes(obj: bytes) -> str:
    return base64.b64encode(obj).decode("utf-8")


def _serialize_set(obj: set) -> list:
    return list(obj)


def _serialize_frozenset(obj: frozenset) -> list:
    return list(obj)


# Type handler registry
_TYPE_HANDLERS: Dict[Type, Callable] = {
    datetime: _serialize_datetime,
    date: _serialize_date,
    time: _serialize_time,
    UUID: _serialize_uuid,
    Decimal: _serialize_decimal,
    Enum: _serialize_enum,
    bytes: _serialize_bytes,
    set: _serialize_set,
    frozenset: _serialize_frozenset,
}


def _load_custom_serializers():
    """Load custom serializers from container if available."""
    global _serializers_loaded

    if _serializers_loaded:
        return

    try:
        container = get_container()

        if container.has_by_name("json_serializers"):
            custom_serializers_dict = container.get_by_name("json_serializers")
            _custom_serializers.update(custom_serializers_dict)
            logger.debug(
                f"Loaded {len(custom_serializers_dict)} custom JSON serializers"
            )
    except (RuntimeError, ImportError):
        # Container not initialized or not available - this is fine
        pass

    _serializers_loaded = True


class MitsukiJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles common Python types not supported by default.

    Supports:
    - datetime, date, time -> ISO format strings
    - UUID -> string
    - Decimal -> float
    - Enum -> value
    - dataclass -> dict
    - bytes -> base64 string
    - set, frozenset -> list
    - Custom registered types
    """

    def default(self, obj: Any) -> Any:
        """Convert obj to a JSON-serializable type."""

        # Load custom serializers from container on first use
        _load_custom_serializers()

        # Check custom serializers first
        obj_type = type(obj)
        if obj_type in _custom_serializers:
            return _custom_serializers[obj_type](obj)

        # Check built-in type handlers
        if obj_type in _TYPE_HANDLERS:
            return _TYPE_HANDLERS[obj_type](obj)

        # Handle Enum subclasses (check isinstance since Enum is base class)
        if isinstance(obj, Enum):
            return obj.value

        # Handle dataclass
        if is_dataclass(obj):
            return _serialize_dataclass(obj)

        # Fallback: try __dict__ for custom objects
        if hasattr(obj, "__dict__"):
            return obj.__dict__

        # Let json.JSONEncoder raise TypeError
        return super().default(obj)


def serialize_json(data: Any, indent: int = None) -> str:
    """
    Serialize data to JSON string using orjson with fallback to MitsukiJSONEncoder.

    Args:
        data: Data to serialize
        indent: Indentation level (None for compact output)

    Returns:
        JSON string

    Raises:
        TypeError: If data contains non-serializable objects
    """
    try:
        if indent is None:
            # orjson.dumps returns bytes, decode to str
            return orjson.dumps(data).decode("utf-8")
        else:
            # orjson doesn't support indent, fall back to stdlib
            return json.dumps(data, cls=MitsukiJSONEncoder, indent=indent)
    except (TypeError, ValueError):
        # Fallback to custom encoder for types orjson doesn't handle
        return json.dumps(data, cls=MitsukiJSONEncoder, indent=indent)


def serialize_json_safe(data: Any, indent: int = None) -> str:
    """
    Serialize data to JSON string with error handling.
    Catches serialization errors and returns a fallback response.

    Args:
        data: Data to serialize
        indent: Indentation level (None for compact output)

    Returns:
        JSON string (or error fallback if serialization fails)
    """
    try:
        return serialize_json(data, indent=indent)
    except (TypeError, ValueError) as e:
        logger.error(f"JSON serialization failed: {e}", exc_info=True)
        # Return a safe fallback
        return json.dumps({"error": "Serialization failed"})


def clear_custom_serializers() -> None:
    """Clear all registered custom serializers and reset load flag. For testing only."""
    global _serializers_loaded
    _custom_serializers.clear()
    _serializers_loaded = False
