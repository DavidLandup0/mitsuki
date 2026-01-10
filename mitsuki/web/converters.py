from typing import Any, Callable, Optional, Union, get_args, get_origin

import msgspec

from mitsuki.exceptions import RequestValidationException

# Sources that yield strings accept these spellings in addition to msgspec's
# native "true"/"false"/"1"/"0".
_BOOL_ALIASES = {"yes": True, "no": False}
_SEQUENCE_ORIGINS = (list, set, frozenset, tuple)


def unwrap_optional(hint: Any) -> Any:
    """Strip NoneType from an Optional/Union hint, returning the core type."""
    if get_origin(hint) is not Union:
        return hint

    args = [arg for arg in get_args(hint) if arg is not type(None)]
    if len(args) == 1:
        return args[0]
    return hint


def is_sequence_hint(hint: Any) -> bool:
    """True if the hint expects a sequence, so repeated values should be collected."""
    core = unwrap_optional(hint)
    origin = get_origin(core) or core
    return origin in _SEQUENCE_ORIGINS


def type_name(hint: Any) -> str:
    """Readable name for a type hint, which may be a typing construct."""
    if isinstance(hint, type):
        return hint.__name__
    return str(hint)


def build_converter(hint: Any) -> Optional[Callable[[Any], Any]]:
    """
    Build a callable converting a raw request value to `hint`.

    Returns None when no conversion is needed - an unannotated parameter or an
    explicit `Any`, where the raw value is passed through untouched.
    """
    if hint is None or hint is Any:
        return None

    name = type_name(hint)

    if unwrap_optional(hint) is bool:

        def convert_bool(value: Any) -> Any:
            if isinstance(value, str):
                aliased = _BOOL_ALIASES.get(value.lower())
                if aliased is not None:
                    return aliased
            try:
                return msgspec.convert(value, hint, strict=False)
            except msgspec.DecodeError as exc:
                raise RequestValidationException(
                    f"Cannot convert '{value}' to {name}: {exc}"
                ) from exc

        return convert_bool

    def convert(value: Any) -> Any:
        try:
            return msgspec.convert(value, hint, strict=False)
        except msgspec.DecodeError as exc:
            raise RequestValidationException(
                f"Cannot convert '{value}' to {name}: {exc}"
            ) from exc

    return convert


def decode_json(body: bytes, hint: Optional[Any]) -> Any:
    """
    Decode a JSON body, validating against `hint` when one is given.

    Parsing and validation happen in a single pass.
    """
    try:
        if hint is None or hint is Any:
            return msgspec.json.decode(body)
        return msgspec.json.decode(body, type=hint, strict=False)
    except msgspec.DecodeError as exc:
        raise RequestValidationException(f"Invalid request body: {exc}") from exc
