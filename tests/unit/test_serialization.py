"""
Tests for JSON serialization module.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Type
from uuid import UUID, uuid4

from mitsuki.config.properties import reload_config
from mitsuki.core.container import DIContainer, get_container, set_container
from mitsuki.core.decorators import Configuration, Provider
from mitsuki.core.enums import Scope
from mitsuki.core.providers import initialize_configuration_providers
from mitsuki.web.serialization import (
    MitsukiJSONEncoder,
    clear_custom_serializers,
    serialize_json,
    serialize_json_safe,
)


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


@dataclass
class Person:
    name: str
    age: int


class CustomObject:
    def __init__(self, value):
        self.value = value


class TestMitsukiJSONEncoder:
    """Tests for MitsukiJSONEncoder."""

    def test_serialize_datetime(self):
        """Test datetime serialization."""
        dt = datetime(2025, 1, 15, 12, 30, 45)
        result = json.dumps(dt, cls=MitsukiJSONEncoder)
        assert result == '"2025-01-15T12:30:45"'

    def test_serialize_date(self):
        """Test date serialization."""
        d = date(2025, 1, 15)
        result = json.dumps(d, cls=MitsukiJSONEncoder)
        assert result == '"2025-01-15"'

    def test_serialize_time(self):
        """Test time serialization."""
        t = time(12, 30, 45)
        result = json.dumps(t, cls=MitsukiJSONEncoder)
        assert result == '"12:30:45"'

    def test_serialize_uuid(self):
        """Test UUID serialization."""
        u = UUID("12345678-1234-5678-1234-567812345678")
        result = json.dumps(u, cls=MitsukiJSONEncoder)
        assert result == '"12345678-1234-5678-1234-567812345678"'

    def test_serialize_decimal(self):
        """Test Decimal serialization."""
        d = Decimal("19.99")
        result = json.dumps(d, cls=MitsukiJSONEncoder)
        assert result == "19.99"

    def test_serialize_enum(self):
        """Test Enum serialization."""
        c = Color.RED
        result = json.dumps(c, cls=MitsukiJSONEncoder)
        assert result == '"red"'

    def test_serialize_dataclass(self):
        """Test dataclass serialization."""
        p = Person(name="Alice", age=30)
        result = json.dumps(p, cls=MitsukiJSONEncoder)
        parsed = json.loads(result)
        assert parsed == {"name": "Alice", "age": 30}

    def test_serialize_bytes(self):
        """Test bytes serialization."""
        b = b"hello"
        result = json.dumps(b, cls=MitsukiJSONEncoder)
        # base64 encoded "hello" is "aGVsbG8="
        assert result == '"aGVsbG8="'

    def test_serialize_set(self):
        """Test set serialization."""
        s = {1, 2, 3}
        result = json.dumps(s, cls=MitsukiJSONEncoder)
        parsed = json.loads(result)
        assert sorted(parsed) == [1, 2, 3]

    def test_serialize_frozenset(self):
        """Test frozenset serialization."""
        fs = frozenset([1, 2, 3])
        result = json.dumps(fs, cls=MitsukiJSONEncoder)
        parsed = json.loads(result)
        assert sorted(parsed) == [1, 2, 3]

    def test_serialize_object_with_dict(self):
        """Test custom object with __dict__ fallback."""
        obj = CustomObject(value=42)
        result = json.dumps(obj, cls=MitsukiJSONEncoder)
        parsed = json.loads(result)
        assert parsed == {"value": 42}

    def test_serialize_nested_structure(self):
        """Test nested structures with multiple types."""
        data = {
            "timestamp": datetime(2025, 1, 15, 12, 0, 0),
            "id": uuid4(),
            "price": Decimal("99.99"),
            "color": Color.BLUE,
            "person": Person(name="Bob", age=25),
            "tags": {"python", "fastapi"},
        }
        result = serialize_json(data)
        parsed = json.loads(result)

        assert "timestamp" in parsed
        assert "id" in parsed
        assert parsed["price"] == 99.99
        assert parsed["color"] == "blue"
        assert parsed["person"]["name"] == "Bob"
        assert set(parsed["tags"]) == {"python", "fastapi"}


class TestSerializeJson:
    """Tests for serialize_json function."""

    def test_serialize_simple_dict(self):
        """Test serializing simple dict."""
        data = {"message": "Hello, World!"}
        result = serialize_json(data)
        # Parse and compare structure (orjson uses compact format without spaces)
        assert json.loads(result) == data

    def test_serialize_with_indent(self):
        """Test serializing with indentation."""
        data = {"name": "Alice", "age": 30}
        result = serialize_json(data, indent=2)
        assert "  " in result
        assert "\n" in result

    def test_serialize_datetime_in_dict(self):
        """Test datetime in dict."""
        data = {"created_at": datetime(2025, 1, 15)}
        result = serialize_json(data)
        assert "2025-01-15" in result

    def test_serialize_object_uses_dict_fallback(self):
        """Test that objects with __dict__ are serialized via fallback."""

        class SimpleObject:
            pass

        obj = SimpleObject()
        obj.value = 42
        result = serialize_json(obj)
        parsed = json.loads(result)
        assert parsed == {"value": 42}


class TestSerializeJsonSafe:
    """Tests for serialize_json_safe function."""

    def test_safe_serialize_simple_dict(self):
        """Test safe serialization of simple dict."""
        data = {"message": "Hello"}
        result = serialize_json_safe(data)
        # Parse and compare structure (orjson uses compact format)
        assert json.loads(result) == data

    def test_safe_serialize_returns_fallback_on_error(self):
        """Test that safe serialization returns fallback on error."""
        # Create circular reference which will fail
        obj = {}
        obj["self"] = obj
        result = serialize_json_safe(obj)
        parsed = json.loads(result)
        assert parsed == {"error": "Serialization failed"}

    def test_safe_serialize_with_datetime(self):
        """Test safe serialization with datetime."""
        data = {"timestamp": datetime(2025, 1, 15)}
        result = serialize_json_safe(data)
        assert "2025-01-15" in result


class TestCustomSerializers:
    """Tests for custom serializer registration via @Provider."""

    def setup_method(self):
        """Reset container and config before each test."""
        set_container(DIContainer())
        reload_config()
        clear_custom_serializers()

    def teardown_method(self):
        """Clear custom serializers after each test."""
        clear_custom_serializers()

    def test_custom_serializer_via_provider(self):
        """Test registering custom serializers via @Provider."""

        class Point:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        @Configuration
        class SerializationConfig:
            @Provider(name="json_serializers")
            def custom_serializers(self) -> Dict[Type, Callable[[Any], Any]]:
                return {Point: lambda p: {"x": p.x, "y": p.y}}

        container = get_container()
        container.register(
            SerializationConfig, name="SerializationConfig", scope=Scope.SINGLETON
        )
        initialize_configuration_providers()

        point = Point(10, 20)
        result = serialize_json(point)
        parsed = json.loads(result)
        assert parsed == {"x": 10, "y": 20}

    def test_custom_serializer_overrides_default(self):
        """Test that custom serializer takes precedence over built-in."""

        class CustomType:
            def __init__(self, value):
                self.value = value

        @Configuration
        class SerializationConfig:
            @Provider(name="json_serializers")
            def custom_serializers(self) -> Dict[Type, Callable[[Any], Any]]:
                return {CustomType: lambda obj: f"custom-{obj.value}"}

        container = get_container()
        container.register(
            SerializationConfig, name="SerializationConfig", scope=Scope.SINGLETON
        )
        initialize_configuration_providers()

        obj = CustomType("test")
        result = serialize_json(obj)
        assert result == '"custom-test"'

    def test_multiple_custom_serializers(self):
        """Test registering multiple custom serializers."""

        class Point:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        class Circle:
            def __init__(self, radius):
                self.radius = radius

        @Configuration
        class SerializationConfig:
            @Provider(name="json_serializers")
            def custom_serializers(self) -> Dict[Type, Callable[[Any], Any]]:
                return {
                    Point: lambda p: [p.x, p.y],
                    Circle: lambda c: {"radius": c.radius},
                }

        container = get_container()
        container.register(
            SerializationConfig, name="SerializationConfig", scope=Scope.SINGLETON
        )
        initialize_configuration_providers()

        data = {"point": Point(5, 10), "circle": Circle(15)}
        result = serialize_json(data)
        parsed = json.loads(result)

        assert parsed["point"] == [5, 10]
        assert parsed["circle"] == {"radius": 15}

    def test_no_provider_uses_defaults(self):
        """Test that serialization works without custom provider."""

        @Configuration
        class EmptyConfig:
            pass

        container = get_container()
        container.register(EmptyConfig, name="EmptyConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        # Should still serialize built-in types
        data = {"timestamp": datetime(2025, 1, 15), "value": 42}
        result = serialize_json(data)
        parsed = json.loads(result)

        assert "2025-01-15" in parsed["timestamp"]
        assert parsed["value"] == 42


class TestIntegrationWithControllers:
    """Test that serialization works in realistic scenarios."""

    def test_api_response_with_mixed_types(self):
        """Test API response with various types."""
        response = {
            "id": uuid4(),
            "created_at": datetime.now(),
            "updated_at": date.today(),
            "price": Decimal("19.99"),
            "status": Color.GREEN,
            "user": Person(name="Alice", age=30),
            "tags": {"python", "web"},
            "metadata": {"key": "value"},
        }

        result = serialize_json(response)
        parsed = json.loads(result)

        # Verify all fields are present and serializable
        assert "id" in parsed
        assert "created_at" in parsed
        assert "updated_at" in parsed
        assert parsed["price"] == 19.99
        assert parsed["status"] == "green"
        assert parsed["user"]["name"] == "Alice"
        assert isinstance(parsed["tags"], list)
        assert parsed["metadata"]["key"] == "value"
