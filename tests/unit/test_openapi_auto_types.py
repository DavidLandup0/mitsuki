"""
Tests for automatic type hint extraction in OpenAPI generation.
"""

from dataclasses import dataclass
from unittest.mock import Mock

from mitsuki.openapi.introspector import (
    _infer_request_body_type,
    _infer_response_type,
    extract_operation,
)
from mitsuki.web.params import extract_param_metadata


@dataclass
class User:
    """User model."""

    id: int
    name: str


@dataclass
class CreateRequest:
    """Create request model."""

    name: str


class TestAutoTypeExtraction:
    """Test automatic type hint extraction from method signatures."""

    def test_infer_response_type_from_return_annotation(self):
        """Test that return type annotations are correctly extracted."""

        async def handler() -> User:
            return User(id=1, name="Test")

        response_type = _infer_response_type(handler)
        assert response_type == User

    def test_infer_response_type_list(self):
        """Test that list return types are correctly extracted."""

        async def handler() -> list[User]:
            return []

        response_type = _infer_response_type(handler)
        assert response_type == list[User]

    def test_infer_response_type_dict(self):
        """Test that dict return types are correctly extracted."""

        async def handler() -> dict:
            return {}

        response_type = _infer_response_type(handler)
        assert response_type == dict

    def test_infer_response_type_none(self):
        """Test that methods without return annotation return None."""

        async def handler():
            return {}

        response_type = _infer_response_type(handler)
        assert response_type is None

    def test_infer_request_body_type_from_body_param(self):
        """Test that body parameter types are correctly extracted."""

        async def handler(body: CreateRequest) -> User:
            return User(id=1, name=body.name)

        param_metadata = extract_param_metadata(handler)
        request_type = _infer_request_body_type(handler, param_metadata)
        assert request_type == CreateRequest

    def test_infer_request_body_type_none(self):
        """Test that methods without body params return None."""

        async def handler(user_id: int) -> User:
            return User(id=user_id, name="Test")

        param_metadata = extract_param_metadata(handler)
        request_type = _infer_request_body_type(handler, param_metadata)
        assert request_type is None

    def test_extract_operation_with_auto_types(self):
        """Test that extract_operation correctly uses inferred types."""

        async def handler(body: CreateRequest) -> User:
            """Create a user."""
            return User(id=1, name=body.name)

        # Mock route metadata without explicit consumes_type or produces_type
        route_meta = Mock()
        route_meta.consumes_type = None
        route_meta.produces_type = None
        route_meta.consumes = "application/json"
        route_meta.produces = "application/json"

        operation = extract_operation(handler, route_meta, "UserController")

        # Verify request body was inferred
        assert "requestBody" in operation
        assert operation["requestBody"]["required"] is True
        assert "application/json" in operation["requestBody"]["content"]
        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert "$ref" in schema
        assert "CreateRequest" in schema["$ref"]

        # Verify response was inferred
        assert "200" in operation["responses"]
        response_schema = operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert "$ref" in response_schema
        assert "User" in response_schema["$ref"]

    def test_explicit_types_override_inferred(self):
        """Test that explicit @Consumes/@Produces override inferred types."""

        @dataclass
        class OverrideRequest:
            value: str

        @dataclass
        class OverrideResponse:
            result: str

        async def handler(body: CreateRequest) -> User:
            """Handler with type hints that should be overridden."""
            return User(id=1, name=body.name)

        # Mock route metadata WITH explicit types (should override)
        route_meta = Mock()
        route_meta.consumes_type = OverrideRequest
        route_meta.produces_type = OverrideResponse
        route_meta.consumes = "application/json"
        route_meta.produces = "application/json"

        operation = extract_operation(handler, route_meta, "UserController")

        # Verify explicit types are used, not inferred ones
        request_schema = operation["requestBody"]["content"]["application/json"][
            "schema"
        ]
        assert "OverrideRequest" in request_schema["$ref"]

        response_schema = operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert "OverrideResponse" in response_schema["$ref"]
