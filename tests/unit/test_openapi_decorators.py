"""
Unit tests for the OpenAPI metadata decorators.
"""

from mitsuki.openapi.decorators import (
    OpenAPIOperation,
    OpenAPISecurity,
    OpenAPITag,
)


class TestOpenAPIOperation:
    """Tests for @OpenAPIOperation."""

    def test_returns_function_unchanged(self):
        """Decorator must return the original function object."""

        async def handler():
            return {}

        decorated = OpenAPIOperation(summary="Test")(handler)

        assert decorated is handler

    def test_all_fields_recorded(self):
        @OpenAPIOperation(
            summary="Get user",
            description="Retrieve a user",
            tags=["Users"],
            responses={404: {"description": "Not found"}},
            parameters=[{"name": "id", "in": "path"}],
            deprecated=True,
            operation_id="getUser",
        )
        async def handler():
            return {}

        assert handler.__mitsuki_openapi_operation__ == {
            "summary": "Get user",
            "description": "Retrieve a user",
            "tags": ["Users"],
            "responses": {404: {"description": "Not found"}},
            "parameters": [{"name": "id", "in": "path"}],
            "deprecated": True,
            "operation_id": "getUser",
        }

    def test_optional_fields_default_to_none(self):
        @OpenAPIOperation()
        async def handler():
            return {}

        metadata = handler.__mitsuki_openapi_operation__

        assert metadata["summary"] is None
        assert metadata["description"] is None
        assert metadata["tags"] is None
        assert metadata["operation_id"] is None
        assert metadata["deprecated"] is False

    def test_empty_responses_and_parameters_are_normalized(self):
        """`responses or {}` and `parameters or []` guard against None."""

        @OpenAPIOperation(responses=None, parameters=None)
        async def handler():
            return {}

        metadata = handler.__mitsuki_openapi_operation__

        assert metadata["responses"] == {}
        assert metadata["parameters"] == []

    def test_deprecated_defaults_to_false(self):
        @OpenAPIOperation(summary="Test")
        async def handler():
            return {}

        assert handler.__mitsuki_openapi_operation__["deprecated"] is False

    def test_decorating_twice_outermost_wins(self):
        """Decorators apply bottom-up, so the topmost decorator wins."""

        @OpenAPIOperation(summary="First")
        @OpenAPIOperation(summary="Second")
        async def handler():
            return {}

        assert handler.__mitsuki_openapi_operation__["summary"] == "First"


class TestOpenAPITag:
    """Tests for @OpenAPITag."""

    def test_returns_class_unchanged(self):
        class Controller:
            pass

        decorated = OpenAPITag(name="Users")(Controller)

        assert decorated is Controller

    def test_all_fields_recorded(self):
        @OpenAPITag(
            name="Users",
            description="User management",
            external_docs={"description": "Guide", "url": "https://example.com"},
        )
        class UserController:
            pass

        assert UserController.__mitsuki_openapi_tag__ == {
            "name": "Users",
            "description": "User management",
            "externalDocs": {"description": "Guide", "url": "https://example.com"},
        }

    def test_optional_fields_default_to_none(self):
        @OpenAPITag(name="Users")
        class UserController:
            pass

        assert UserController.__mitsuki_openapi_tag__ == {
            "name": "Users",
            "description": None,
            "externalDocs": None,
        }


class TestOpenAPISecurity:
    """Tests for @OpenAPISecurity."""

    def test_returns_function_unchanged(self):
        async def handler():
            return {}

        decorated = OpenAPISecurity(["bearerAuth"])(handler)

        assert decorated is handler

    def test_schemes_recorded(self):
        @OpenAPISecurity(["bearerAuth", "apiKey"])
        async def handler():
            return {}

        assert handler.__mitsuki_openapi_security__ == ["bearerAuth", "apiKey"]

    def test_empty_scheme_list_recorded(self):
        @OpenAPISecurity([])
        async def handler():
            return {}

        assert handler.__mitsuki_openapi_security__ == []
