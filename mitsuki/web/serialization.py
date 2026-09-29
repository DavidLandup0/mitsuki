import logging
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Type
from uuid import UUID

import msgspec

from mitsuki.core.container import get_container

logger = logging.getLogger(__name__)

# Registry for custom type serializers
_custom_serializers: Dict[Type, Callable[[Any], Any]] = {}
_serializers_loaded = False

# Types msgspec encodes on its own. A custom serializer for one of these has to
# be applied before encoding, because the encode hook is only consulted for
# types msgspec cannot handle.
_NATIVELY_ENCODED = (
    datetime,
    date,
    time,
    UUID,
    Decimal,
    bytes,
    bytearray,
    set,
    frozenset,
    Enum,
)

# Types to_builtins leaves untouched so the encoder formats them itself.
_BUILTIN_PASSTHROUGH = (datetime, date, time, UUID, Decimal, bytes, bytearray)

# True when a registered serializer targets a natively encoded type, which is
# the only case that needs the pre-pass below.
_overrides_native = False


def _refresh_override_flag():
    """Record whether any serializer overrides a natively encoded type."""
    global _overrides_native

    _overrides_native = any(
        issubclass(type_, _NATIVELY_ENCODED) or is_dataclass(type_)
        for type_ in _custom_serializers
    )


def _apply_custom_serializers(obj: Any) -> Any:
    """
    Apply custom serializers ahead of encoding.

    Only used when a serializer targets a type msgspec would otherwise encode
    itself, so that a registered serializer always wins over the built-in
    handling regardless of what else is in the payload.
    """
    serializer = _custom_serializers.get(type(obj))
    if serializer:
        return serializer(obj)

    if isinstance(obj, dict):
        return {key: _apply_custom_serializers(value) for key, value in obj.items()}

    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_apply_custom_serializers(value) for value in obj]

    if is_dataclass(obj) and not isinstance(obj, type):
        return {
            field.name: _apply_custom_serializers(getattr(obj, field.name))
            for field in fields(obj)
        }

    return obj


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

    _refresh_override_flag()
    _serializers_loaded = True


def _encode_unsupported(obj: Any) -> Any:
    """
    Convert a value msgspec cannot encode natively.

    vars() raises TypeError for objects without a __dict__, which is what
    msgspec expects from an encode hook that cannot handle the value.
    """
    _load_custom_serializers()

    serializer = _custom_serializers.get(type(obj))
    if serializer:
        return serializer(obj)

    return vars(obj)


# decimal_format="number" keeps Decimal as a JSON number rather than a string.
_encoder = msgspec.json.Encoder(decimal_format="number", enc_hook=_encode_unsupported)


def to_builtins(data: Any) -> Any:
    """Convert data to the dicts, lists and scalars that serialize_json encodes."""
    _load_custom_serializers()

    if _overrides_native:
        data = _apply_custom_serializers(data)

    return msgspec.to_builtins(
        data, builtin_types=_BUILTIN_PASSTHROUGH, enc_hook=_encode_unsupported
    )


def serialize_json(data: Any, indent: int = None) -> str:
    """
    Serialize data to a JSON string.

    Args:
        data: Data to serialize
        indent: Indentation level (None for compact output)

    Returns:
        JSON string

    Raises:
        TypeError: If data contains non-serializable objects
    """
    _load_custom_serializers()

    if _overrides_native:
        data = _apply_custom_serializers(data)

    encoded = _encoder.encode(data)

    if indent is not None:
        encoded = msgspec.json.format(encoded, indent=indent)

    return encoded.decode("utf-8")


def serialize_json_safe(data: Any, indent: int = None) -> str:
    """
    Serialize data to a JSON string, returning a fallback on failure.

    Args:
        data: Data to serialize
        indent: Indentation level (None for compact output)

    Returns:
        JSON string (or error fallback if serialization fails)
    """
    try:
        return serialize_json(data, indent=indent)
    except (TypeError, ValueError, RecursionError) as e:
        logger.error(f"JSON serialization failed: {e}", exc_info=True)
        return '{"error": "Serialization failed"}'


def clear_custom_serializers() -> None:
    """Clear all registered custom serializers and reset load flag. For testing only."""
    global _serializers_loaded
    _custom_serializers.clear()
    _refresh_override_flag()
    _serializers_loaded = False
