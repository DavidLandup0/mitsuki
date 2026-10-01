"""
Unit tests for OpenAPI introspection of controllers, routes, and parameters.
"""

from dataclasses import dataclass
from unittest.mock import Mock

import pytest
from starlette.requests import Request

from mitsuki import (
    DeleteMapping,
    GetMapping,
    PathVariable,
    PostMapping,
    PutMapping,
    QueryParam,
    RequestBody,
    RequestHeader,
    RestController,
)
from mitsuki.openapi.decorators import OpenAPIOperation
from mitsuki.openapi.introspector import (
    _combine_paths,
    _infer_request_body_type,
    _infer_response_type,
    _param_to_openapi,
    extract_operation,
    extract_paths,
)
from mitsuki.openapi.schemas import clear_schema_registry
from mitsuki.web.params import ParamMetadata, extract_param_metadata


@dataclass
class User:
    """Response model."""

    id: int
    name: str


@dataclass
class CreateUser:
    """Request body model."""

    name: str


@pytest.fixture(autouse=True)
def clean_registry():
    """The schema registry is module-level state; isolate every test."""
    clear_schema_registry()
    yield
    clear_schema_registry()


class TestCombinePaths:
    """Tests for _combine_paths."""

    def test_base_and_route(self):
        assert _combine_paths("/api", "/users") == "/api/users"

    def test_trailing_slashes_stripped(self):
        assert _combine_paths("/api/", "/users/") == "/api/users"

    def test_empty_route_returns_base(self):
        assert _combine_paths("/api", "") == "/api"

    def test_empty_route_and_base_returns_root(self):
        assert _combine_paths("", "") == "/"

    def test_empty_base_returns_route(self):
        assert _combine_paths("", "/users") == "/users"

    def test_empty_route_on_root_base(self):
        assert _combine_paths("/", "") == "/"


class TestInferResponseType:
    """Tests for _infer_response_type."""

    def test_reads_return_annotation(self):
        async def handler() -> User:
            return User(id=1, name="Test")

        assert _infer_response_type(handler) is User

    def test_returns_none_without_annotation(self):
        async def handler():
            return {}

        assert _infer_response_type(handler) is None

    def test_skips_explicit_none_annotation(self):
        async def handler() -> None:
            return None

        assert _infer_response_type(handler) is None

    def test_unresolvable_annotation_falls_back_to_none(self):
        """An unresolvable forward reference makes get_type_hints raise."""

        async def handler() -> "DoesNotExist":  # noqa: F821
            return None

        assert _infer_response_type(handler) is None

    def test_list_of_models(self):
        async def handler() -> list[User]:
            return []

        assert _infer_response_type(handler) == list[User]


class TestInferRequestBodyType:
    """Tests for _infer_request_body_type."""

    def test_reads_body_parameter_type(self):
        async def handler(body: CreateUser = RequestBody()) -> User:
            return User(id=1, name=body.name)

        metadata = extract_param_metadata(handler)

        assert _infer_request_body_type(handler, metadata) is CreateUser

    def test_returns_none_without_body_parameter(self):
        async def handler(user_id: int = PathVariable()) -> User:
            return User(id=user_id, name="Test")

        metadata = extract_param_metadata(handler)

        assert _infer_request_body_type(handler, metadata) is None


class TestParamToOpenAPI:
    """Tests for _param_to_openapi."""

    def test_path_parameter(self):
        async def handler(user_id: int = PathVariable()):
            return {}

        metadata = extract_param_metadata(handler)["user_id"]

        assert _param_to_openapi("user_id", metadata) == {
            "name": "user_id",
            "in": "path",
            "required": True,
            "schema": {"type": "integer"},
        }

    def test_query_parameter_with_default(self):
        async def handler(limit: int = QueryParam(default=10)):
            return {}

        metadata = extract_param_metadata(handler)["limit"]

        assert _param_to_openapi("limit", metadata) == {
            "name": "limit",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "default": 10},
        }

    def test_explicit_name_overrides_parameter_name(self):
        async def handler(page: int = QueryParam(name="page_number")):
            return {}

        metadata = extract_param_metadata(handler)["page"]

        assert _param_to_openapi("page", metadata)["name"] == "page_number"

    def test_header_parameter_uses_metadata_name(self):
        async def handler(token: str = RequestHeader(name="X-Token")):
            return {}

        metadata = extract_param_metadata(handler)["token"]

        assert _param_to_openapi("token", metadata)["name"] == "X-Token"

    def test_optional_query_parameter_is_not_required(self):
        async def handler(q: str = QueryParam(required=False)):
            return {}

        metadata = extract_param_metadata(handler)["q"]

        assert _param_to_openapi("q", metadata)["required"] is False

    def test_any_annotated_parameter_becomes_object(self):
        """An absent annotation resolves to Any, which has no scalar schema."""

        async def handler(q=QueryParam()):
            return {}

        metadata = extract_param_metadata(handler)["q"]

        assert _param_to_openapi("q", metadata)["schema"] == {"type": "object"}

    def test_missing_param_type_defaults_to_string(self):
        """When param_type is None the converter falls back to string."""

        metadata = ParamMetadata(kind="query", name="q", required=False)

        assert _param_to_openapi("q", metadata)["schema"] == {"type": "string"}

    def test_body_parameter_returns_none(self):
        """Body params have no 'in' location; requestBody handles them."""

        async def handler(body: CreateUser = RequestBody()):
            return {}

        metadata = extract_param_metadata(handler)["body"]

        assert _param_to_openapi("body", metadata) is None


class TestExtractOperationDefaults:
    """Tests for inferred defaults in extract_operation."""

    def build_route(self, **overrides):
        route = Mock()
        route.method = "GET"
        route.path = "/users"
        route.produces = "application/json"
        route.consumes = "application/json"
        route.produces_type = None
        route.consumes_type = None
        for key, value in overrides.items():
            setattr(route, key, value)
        return route

    def test_summary_derived_from_method_name(self):
        async def get_user_by_id(self):
            return {}

        operation = extract_operation(
            get_user_by_id, self.build_route(), "UserController"
        )

        assert operation["summary"] == "Get User By Id"

    def test_operation_id_derived_from_controller_and_method(self):
        async def list_users(self):
            return {}

        operation = extract_operation(list_users, self.build_route(), "UserController")

        assert operation["operationId"] == "UserController_list_users"

    def test_tag_defaults_to_controller_name(self):
        async def handler(self):
            return {}

        operation = extract_operation(handler, self.build_route(), "UserController")

        assert operation["tags"] == ["UserController"]

    def test_description_from_docstring(self):
        async def handler(self):
            """Fetch a thing."""
            return {}

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["description"] == "Fetch a thing."

    def test_description_omitted_when_absent(self):
        async def handler(self):
            return {}

        operation = extract_operation(handler, self.build_route(), "C")

        assert "description" not in operation

    def test_deprecated_flag_absent_by_default(self):
        async def handler(self):
            return {}

        operation = extract_operation(handler, self.build_route(), "C")

        assert "deprecated" not in operation

    def test_default_responses_present(self):
        async def handler(self) -> User:
            return User(id=1, name="Test")

        operation = extract_operation(handler, self.build_route(), "C")

        assert set(operation["responses"]) == {"200", "400", "500"}
        assert operation["responses"]["400"]["description"] == "Bad request"
        assert operation["responses"]["500"]["description"] == "Internal server error"

    def test_default_response_schema_without_annotation(self):
        async def handler(self):
            return {}

        operation = extract_operation(handler, self.build_route(), "C")

        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema == {"type": "object"}

    def test_custom_produces_media_type(self):
        async def handler(self) -> User:
            return User(id=1, name="Test")

        route = self.build_route(produces="application/xml")
        operation = extract_operation(handler, route, "C")

        assert "application/xml" in operation["responses"]["200"]["content"]

    def test_custom_consumes_media_type(self):
        async def handler(body: CreateUser = RequestBody()) -> User:
            return User(id=1, name=body.name)

        route = self.build_route(consumes="application/vnd.api+json")
        operation = extract_operation(handler, route, "C")

        assert "application/vnd.api+json" in operation["requestBody"]["content"]

    def test_default_consumes_media_type(self):
        async def handler(body: CreateUser = RequestBody()) -> User:
            return User(id=1, name=body.name)

        route = self.build_route(consumes=None)
        operation = extract_operation(handler, route, "C")

        assert "application/json" in operation["requestBody"]["content"]

    def test_no_request_body_without_body_param(self):
        async def handler(self) -> User:
            return User(id=1, name="Test")

        operation = extract_operation(handler, self.build_route(), "C")

        assert "requestBody" not in operation

    def test_query_and_path_parameters_included(self):
        async def handler(
            self,
            user_id: int = PathVariable(),
            limit: int = QueryParam(default=20),
        ) -> User:
            return User(id=user_id, name="Test")

        operation = extract_operation(handler, self.build_route(), "C")

        locations = {p["name"]: p["in"] for p in operation["parameters"]}
        assert locations == {"user_id": "path", "limit": "query"}

    def test_header_parameter_included(self):
        async def handler(token: str = RequestHeader(name="X-Token")) -> User:
            return User(id=1, name=token)

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["parameters"][0]["in"] == "header"

    def test_body_param_excluded_from_parameters_list(self):
        async def handler(body: CreateUser = RequestBody()) -> User:
            return User(id=1, name=body.name)

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["parameters"] == []


class TestExtractOperationDecoratorOverrides:
    """Tests for @OpenAPIOperation metadata merging."""

    def build_route(self):
        route = Mock()
        route.method = "GET"
        route.path = "/users"
        route.produces = "application/json"
        route.consumes = "application/json"
        route.produces_type = None
        route.consumes_type = None
        return route

    def test_decorator_summary_wins(self):
        @OpenAPIOperation(summary="Custom summary")
        async def handler(self):
            return {}

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["summary"] == "Custom summary"

    def test_decorator_description_wins_over_docstring(self):
        @OpenAPIOperation(description="Decorator description")
        async def handler(self):
            """Docstring description."""
            return {}

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["description"] == "Decorator description"

    def test_decorator_tags_win(self):
        @OpenAPIOperation(tags=["Users", "Admin"])
        async def handler(self):
            return {}

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["tags"] == ["Users", "Admin"]

    def test_decorator_operation_id_wins(self):
        @OpenAPIOperation(operation_id="customId")
        async def handler(self):
            return {}

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["operationId"] == "customId"

    def test_deprecated_flag_set(self):
        @OpenAPIOperation(deprecated=True)
        async def handler(self):
            return {}

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["deprecated"] is True

    def test_custom_responses_added(self):
        @OpenAPIOperation(responses={404: {"description": "Not found"}})
        async def handler(self) -> User:
            return User(id=1, name="Test")

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["responses"]["404"] == {"description": "Not found"}

    def test_custom_response_overrides_generated(self):
        @OpenAPIOperation(responses={200: {"description": "Custom OK"}})
        async def handler(self) -> User:
            return User(id=1, name="Test")

        operation = extract_operation(handler, self.build_route(), "C")

        assert operation["responses"]["200"] == {"description": "Custom OK"}

    def test_decorator_param_merged_into_existing(self):
        @OpenAPIOperation(
            parameters=[{"name": "limit", "description": "Page size", "required": None}]
        )
        async def handler(self, limit: int = QueryParam(default=20)) -> User:
            return User(id=1, name="Test")

        operation = extract_operation(handler, self.build_route(), "C")

        limit = next(p for p in operation["parameters"] if p["name"] == "limit")
        assert limit["description"] == "Page size"
        assert limit["in"] == "query"

    def test_none_values_in_merge_do_not_clobber(self):
        """The merge filters `v is not None`, so existing values survive."""

        @OpenAPIOperation(parameters=[{"name": "limit", "description": None}])
        async def handler(self, limit: int = QueryParam(default=20)) -> User:
            return User(id=1, name="Test")

        operation = extract_operation(handler, self.build_route(), "C")

        limit = next(p for p in operation["parameters"] if p["name"] == "limit")
        assert "description" not in limit
        assert limit["required"] is False

    def test_decorator_only_param_added(self):
        @OpenAPIOperation(parameters=[{"name": "X-Trace", "in": "header"}])
        async def handler(self) -> User:
            return User(id=1, name="Test")

        operation = extract_operation(handler, self.build_route(), "C")

        assert {"name": "X-Trace", "in": "header"} in operation["parameters"]

    def test_explicit_consumes_type_overrides_inference(self):
        @dataclass
        class OverrideRequest:
            value: str

        async def handler(body: CreateUser = RequestBody()) -> User:
            return User(id=1, name=body.name)

        route = self.build_route()
        route.consumes_type = OverrideRequest

        operation = extract_operation(handler, route, "C")

        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert schema["$ref"] == "#/components/schemas/OverrideRequest"

    def test_explicit_produces_type_overrides_inference(self):
        @dataclass
        class OverrideResponse:
            result: str

        async def handler(self) -> User:
            return User(id=1, name="Test")

        route = self.build_route()
        route.produces_type = OverrideResponse

        operation = extract_operation(handler, route, "C")

        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema["$ref"] == "#/components/schemas/OverrideResponse"


class TestExtractPaths:
    """Tests for extract_paths across a controller class."""

    def test_single_get_route(self):
        @RestController("/api")
        class UserController:
            @GetMapping("/users")
            async def list_users(self) -> User:
                return User(id=1, name="Test")

        paths = extract_paths(UserController, "/api")

        assert set(paths) == {"/api/users"}
        assert set(paths["/api/users"]) == {"get"}

    def test_multiple_verbs_on_same_path_are_merged(self):
        @RestController("/api")
        class UserController:
            @GetMapping("/users")
            async def list_users(self) -> User:
                return User(id=1, name="Test")

            @PostMapping("/users")
            async def create_user(self) -> User:
                return User(id=1, name="Test")

        paths = extract_paths(UserController, "/api")

        assert set(paths["/api/users"]) == {"get", "post"}

    def test_put_and_delete_verbs(self):
        @RestController("/api")
        class UserController:
            @PutMapping("/users/{id}")
            async def update_user(self, id: int = PathVariable()):
                return {}

            @DeleteMapping("/users/{id}")
            async def delete_user(self, id: int = PathVariable()):
                return {}

        paths = extract_paths(UserController, "/api")

        assert set(paths["/api/users/{id}"]) == {"put", "delete"}

    def test_controller_name_used_as_tag(self):
        @RestController("/api")
        class UserController:
            @GetMapping("/users")
            async def list_users(self):
                return {}

        paths = extract_paths(UserController, "/api")

        assert paths["/api/users"]["get"]["tags"] == ["UserController"]

    def test_private_methods_skipped(self):
        @RestController("/api")
        class UserController:
            @GetMapping("/users")
            async def list_users(self):
                return {}

            async def _helper(self):
                return {}

        paths = extract_paths(UserController, "/api")

        assert set(paths) == {"/api/users"}

    def test_undecorated_methods_skipped(self):
        @RestController("/api")
        class UserController:
            @GetMapping("/users")
            async def list_users(self):
                return {}

            async def helper(self):
                return {}

        paths = extract_paths(UserController, "/api")

        assert set(paths) == {"/api/users"}

    def test_empty_base_path(self):
        @RestController()
        class UserController:
            @GetMapping("/users")
            async def list_users(self):
                return {}

        paths = extract_paths(UserController, "")

        assert set(paths) == {"/users"}

    def test_request_injection_is_not_documented(self):
        """An injected Request has no OpenAPI 'in' location."""

        @RestController("/api")
        class UserController:
            @GetMapping("/users")
            async def list_users(self, request: Request):
                return {}

        paths = extract_paths(UserController, "/api")

        assert paths["/api/users"]["get"]["parameters"] == []

    def test_controller_with_no_routes_yields_empty_dict(self):
        @RestController("/api")
        class UserController:
            async def helper(self):
                return {}

        assert extract_paths(UserController, "/api") == {}
