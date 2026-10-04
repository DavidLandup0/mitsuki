"""
Unit tests for OpenAPI JSON Schema conversion.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Union

import pytest

from mitsuki.openapi.schemas import (
    clear_schema_registry,
    dataclass_to_schema,
    enum_to_schema,
    get_schema_registry,
    type_to_schema,
)


class Color(str, Enum):
    """String-backed enum."""

    RED = "red"
    GREEN = "green"


class Priority(int, Enum):
    """Integer-backed enum."""

    LOW = 1
    HIGH = 2


class Ratio(float, Enum):
    """Float-backed enum."""

    HALF = 0.5


class Empty(Enum):
    """Enum with no members."""


class Mixed(Enum):
    """Enum whose first value is neither str, int, nor float."""

    TUPLE = (1, 2)


@dataclass
class Address:
    """Nested dataclass used to exercise $ref registration."""

    street: str
    zipcode: str = "00000"


@dataclass
class Person:
    """Dataclass with optional field, defaults, and metadata."""

    id: int
    name: str = field(metadata={"description": "Full legal name"})
    nickname: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    address: Optional[Address] = None


class PydanticLike:
    """Stand-in for a Pydantic v2 model."""

    @staticmethod
    def model_json_schema():
        return {"type": "object", "title": "PydanticLike"}


class BrokenPydanticLike:
    """Model whose schema generation raises."""

    @staticmethod
    def model_json_schema():
        raise RuntimeError("schema generation failed")


class Plain:
    """Non-dataclass, non-enum class with no schema hook."""


@pytest.fixture(autouse=True)
def clean_registry():
    """The schema registry is module-level state; isolate every test."""
    clear_schema_registry()
    yield
    clear_schema_registry()


class TestPrimitives:
    """Tests for primitive type conversion."""

    def test_int(self):
        assert type_to_schema(int) == {"type": "integer"}

    def test_str(self):
        assert type_to_schema(str) == {"type": "string"}

    def test_float(self):
        assert type_to_schema(float) == {"type": "number"}

    def test_bool(self):
        assert type_to_schema(bool) == {"type": "boolean"}

    def test_none_literal(self):
        assert type_to_schema(None) == {"type": "null"}

    def test_nonetype(self):
        assert type_to_schema(type(None)) == {"type": "null"}

    def test_unknown_type_falls_back_to_object(self):
        assert type_to_schema(Plain) == {"type": "object"}


class TestCollections:
    """Tests for list and dict conversion."""

    def test_typed_list(self):
        assert type_to_schema(List[str]) == {
            "type": "array",
            "items": {"type": "string"},
        }

    def test_bare_typing_list(self):
        assert type_to_schema(List) == {"type": "array", "items": {}}

    def test_list_of_dataclass_uses_ref(self):
        schema = type_to_schema(List[Address])

        assert schema["type"] == "array"
        assert schema["items"] == {"$ref": "#/components/schemas/Address"}
        assert "Address" in get_schema_registry()

    def test_typed_dict(self):
        assert type_to_schema(Dict[str, int]) == {
            "type": "object",
            "additionalProperties": {"type": "integer"},
        }

    def test_single_arg_dict_uses_open_ended_object(self):
        assert type_to_schema(dict[str]) == {
            "type": "object",
            "additionalProperties": True,
        }


class TestUnions:
    """Tests for Union and Optional handling."""

    def test_optional_single_type_is_nullable(self):
        assert type_to_schema(Optional[int]) == {"type": "integer", "nullable": True}

    def test_union_without_none_uses_any_of(self):
        assert type_to_schema(Union[int, str]) == {
            "anyOf": [{"type": "integer"}, {"type": "string"}]
        }

    def test_optional_union_includes_null_member(self):
        # Before Python 3.14, typing caches unions and treats Union[int, str]
        # and Union[str, int] as equal, so member order depends on which was
        # created first in the process. anyOf is unordered, so neither is wrong.
        schema = type_to_schema(Optional[Union[int, str]])

        assert sorted(schema["anyOf"], key=lambda member: member["type"]) == [
            {"type": "integer"},
            {"type": "null"},
            {"type": "string"},
        ]


class TestEnums:
    """Tests for enum conversion and registration."""

    def test_enum_uses_ref_and_registers(self):
        assert type_to_schema(Color) == {"$ref": "#/components/schemas/Color"}
        assert get_schema_registry()["Color"] == {
            "type": "string",
            "enum": ["red", "green"],
            "title": "Color",
        }

    def test_repeated_conversion_does_not_reregister(self):
        type_to_schema(Color)
        registry_after_first = get_schema_registry()

        assert type_to_schema(Color) == {"$ref": "#/components/schemas/Color"}
        assert get_schema_registry() == registry_after_first

    def test_enum_without_refs(self):
        assert type_to_schema(Color, use_refs=False) == {
            "type": "string",
            "enum": ["red", "green"],
            "title": "Color",
        }

    def test_integer_enum_type_detection(self):
        assert enum_to_schema(Priority)["type"] == "integer"

    def test_float_enum_type_detection(self):
        assert enum_to_schema(Ratio)["type"] == "number"

    def test_empty_enum_defaults_to_string(self):
        assert enum_to_schema(Empty) == {"type": "string", "enum": [], "title": "Empty"}

    def test_non_scalar_enum_falls_back_to_string(self):
        assert enum_to_schema(Mixed)["type"] == "string"


class TestDataclasses:
    """Tests for dataclass conversion and registration."""

    def test_dataclass_uses_ref_and_registers(self):
        assert type_to_schema(Address) == {"$ref": "#/components/schemas/Address"}
        assert get_schema_registry()["Address"]["title"] == "Address"

    def test_repeated_conversion_does_not_reregister(self):
        type_to_schema(Address)
        registry_after_first = get_schema_registry()

        assert type_to_schema(Address) == {"$ref": "#/components/schemas/Address"}
        assert get_schema_registry() == registry_after_first

    def test_required_fields_only(self):
        schema = dataclass_to_schema(Address, use_refs=False)

        assert schema["required"] == ["street"]

    def test_dataclass_without_required_fields_omits_key(self):
        @dataclass
        class AllDefaults:
            value: int = 0

        assert "required" not in dataclass_to_schema(AllDefaults)

    def test_field_metadata_becomes_description(self):
        schema = dataclass_to_schema(Person, use_refs=False)

        assert schema["properties"]["name"]["description"] == "Full legal name"

    def test_field_without_metadata_gets_no_description(self):
        schema = dataclass_to_schema(Person, use_refs=False)

        assert "description" not in schema["properties"]["id"]

    def test_optional_and_collection_fields(self):
        properties = dataclass_to_schema(Person, use_refs=False)["properties"]

        assert properties["nickname"] == {"type": "string", "nullable": True}
        assert properties["tags"] == {
            "type": "array",
            "items": {"type": "string"},
        }

    def test_nested_dataclass_ref_when_use_refs_enabled(self):
        properties = dataclass_to_schema(Person)["properties"]

        assert properties["address"] == {
            "$ref": "#/components/schemas/Address",
            "nullable": True,
        }
        assert "Address" in get_schema_registry()

    def test_nested_dataclass_inlined_when_use_refs_disabled(self):
        properties = dataclass_to_schema(Person, use_refs=False)["properties"]

        assert properties["address"]["nullable"] is True
        assert properties["address"]["type"] == "object"
        assert properties["address"]["title"] == "Address"
        assert get_schema_registry() == {}


class TestPydantic:
    """Tests for the Pydantic-style hook."""

    def test_uses_model_json_schema(self):
        assert type_to_schema(PydanticLike) == {
            "type": "object",
            "title": "PydanticLike",
        }

    def test_failing_hook_falls_back_to_object(self):
        assert type_to_schema(BrokenPydanticLike) == {"type": "object"}


class TestRegistry:
    """Tests for registry lifecycle."""

    def test_starts_empty(self):
        assert get_schema_registry() == {}

    def test_returns_copy(self):
        type_to_schema(Address)
        registry = get_schema_registry()
        registry["Injected"] = {}

        assert "Injected" not in get_schema_registry()

    def test_clear_resets_both_stores(self):
        type_to_schema(Address)
        type_to_schema(Color)

        clear_schema_registry()

        assert get_schema_registry() == {}

        # The type cache cleared too, so Address is rebuilt from scratch.
        type_to_schema(Address)
        assert set(get_schema_registry()) == {"Address"}
