"""
Tests for mapping decorator aliases (@Get, @Post, etc.).
"""

from dataclasses import dataclass

import pytest

from mitsuki.core.enums import HttpMethod
from mitsuki.web.mappings import (
    Consumes,
    Delete,
    DeleteMapping,
    Get,
    GetMapping,
    Patch,
    PatchMapping,
    Post,
    PostMapping,
    Produces,
    Put,
    PutMapping,
    RequestMapping,
    RouteMetadata,
)


class TestMappingAliases:
    """Tests for shorter mapping decorator aliases."""

    def test_get_is_alias_for_get_mapping(self):
        """Test that Get is an alias for GetMapping."""
        assert Get is GetMapping

    def test_post_is_alias_for_post_mapping(self):
        """Test that Post is an alias for PostMapping."""
        assert Post is PostMapping

    def test_put_is_alias_for_put_mapping(self):
        """Test that Put is an alias for PutMapping."""
        assert Put is PutMapping

    def test_delete_is_alias_for_delete_mapping(self):
        """Test that Delete is an alias for DeleteMapping."""
        assert Delete is DeleteMapping

    def test_patch_is_alias_for_patch_mapping(self):
        """Test that Patch is an alias for PatchMapping."""
        assert Patch is PatchMapping


class TestAliasUsage:
    """Tests for using the aliases in actual routes."""

    def test_get_decorator_works(self):
        """Test @Get decorator creates route metadata."""

        @Get("/users")
        async def get_users():
            return []

        assert hasattr(get_users, "__mitsuki_route__")
        assert get_users.__mitsuki_route__.method == "GET"
        assert get_users.__mitsuki_route__.path == "/users"

    def test_post_decorator_works(self):
        """Test @Post decorator creates route metadata."""

        @Post("/users")
        async def create_user(data):
            return data

        assert hasattr(create_user, "__mitsuki_route__")
        assert create_user.__mitsuki_route__.method == "POST"
        assert create_user.__mitsuki_route__.path == "/users"

    def test_put_decorator_works(self):
        """Test @Put decorator creates route metadata."""

        @Put("/users/{id}")
        async def update_user(id, data):
            return data

        assert hasattr(update_user, "__mitsuki_route__")
        assert update_user.__mitsuki_route__.method == "PUT"
        assert update_user.__mitsuki_route__.path == "/users/{id}"

    def test_delete_decorator_works(self):
        """Test @Delete decorator creates route metadata."""

        @Delete("/users/{id}")
        async def delete_user(id):
            return {"deleted": True}

        assert hasattr(delete_user, "__mitsuki_route__")
        assert delete_user.__mitsuki_route__.method == "DELETE"
        assert delete_user.__mitsuki_route__.path == "/users/{id}"

    def test_patch_decorator_works(self):
        """Test @Patch decorator creates route metadata."""

        @Patch("/users/{id}")
        async def patch_user(id, data):
            return data

        assert hasattr(patch_user, "__mitsuki_route__")
        assert patch_user.__mitsuki_route__.method == "PATCH"
        assert patch_user.__mitsuki_route__.path == "/users/{id}"


class TestRouteMethodIsTyped:
    """RouteMetadata.method holds an HttpMethod, not a bare string."""

    def test_get_stores_http_method_get(self):
        @Get("/users")
        async def get_users():
            return []

        assert get_users.__mitsuki_route__.method is HttpMethod.GET

    def test_post_stores_http_method_post(self):
        @Post("/users")
        async def create_user(data):
            return data

        assert create_user.__mitsuki_route__.method is HttpMethod.POST

    def test_default_method_of_request_mapping_is_get(self):
        @RequestMapping("/users")
        async def users():
            return []

        assert users.__mitsuki_route__.method is HttpMethod.GET

    def test_method_accepts_an_enum_member(self):
        @RequestMapping("/users", method=HttpMethod.DELETE)
        async def users():
            return []

        assert users.__mitsuki_route__.method is HttpMethod.DELETE

    @pytest.mark.parametrize("spelling", ["delete", "DELETE", "Delete"])
    def test_method_accepts_a_string_in_any_case(self, spelling):
        @RequestMapping("/users", method=spelling)
        async def users():
            return []

        assert users.__mitsuki_route__.method is HttpMethod.DELETE

    def test_unknown_method_is_rejected_at_decoration_time(self):
        with pytest.raises(ValueError, match="Invalid HttpMethod: 'FETCH'"):

            @RequestMapping("/users", method="FETCH")
            async def users():
                return []

    def test_direct_construction_normalizes_a_method_string(self):
        route = RouteMetadata(method="patch", path="/users")

        assert route.method is HttpMethod.PATCH

    def test_direct_construction_rejects_an_unknown_method(self):
        with pytest.raises(ValueError, match="Invalid HttpMethod: 'FETCH'"):
            RouteMetadata(method="FETCH", path="/users")

    def test_starlette_receives_a_plain_method_string(self):
        from starlette.routing import Route

        @Get("/users")
        async def get_users():
            return []

        route = Route(
            path="/users",
            endpoint=get_users,
            methods=[get_users.__mitsuki_route__.method],
        )

        assert route.methods == {"GET", "HEAD"}


class TestAliasWithParameters:
    """Tests for using aliases with validation parameters."""

    def test_get_with_produces_type(self):
        """Test @Get with produces_type parameter."""

        @dataclass
        class UserDTO:
            id: int
            name: str

        @Get("/users", produces_type=UserDTO)
        async def get_users():
            return []

        assert get_users.__mitsuki_route__.produces_type == UserDTO

    def test_post_with_consumes_type(self):
        """Test @Post with consumes_type parameter."""

        @dataclass
        class CreateUserRequest:
            name: str
            email: str

        @Post("/users", consumes_type=CreateUserRequest)
        async def create_user(data):
            return data

        assert create_user.__mitsuki_route__.consumes_type == CreateUserRequest

    def test_get_with_exclude_fields(self):
        """Test @Get with exclude_fields parameter."""

        @Get("/users", exclude_fields=["password", "secret"])
        async def get_users():
            return []

        assert get_users.__mitsuki_route__.exclude_fields == ["password", "secret"]

    def test_post_with_produces_and_consumes(self):
        """Test @Post with both produces_type and consumes_type."""

        @dataclass
        class CreateRequest:
            name: str

        @dataclass
        class Response:
            id: int
            name: str

        @Post("/users", produces_type=Response, consumes_type=CreateRequest)
        async def create_user(data):
            return data

        assert create_user.__mitsuki_route__.produces_type == Response
        assert create_user.__mitsuki_route__.consumes_type == CreateRequest


class TestAliasWithDecorators:
    """Tests for using aliases with @Produces and @Consumes decorators."""

    def test_get_with_produces_decorator(self):
        """Test @Get with @Produces decorator."""

        @dataclass
        class UserDTO:
            id: int
            name: str

        @Get("/users")
        @Produces(UserDTO)
        async def get_users():
            return []

        assert get_users.__mitsuki_route__.produces_type == UserDTO

    def test_post_with_consumes_and_produces_decorators(self):
        """Test @Post with both @Consumes and @Produces decorators."""

        @dataclass
        class CreateRequest:
            name: str

        @dataclass
        class Response:
            id: int
            name: str

        @Post("/users")
        @Produces(Response)
        @Consumes(CreateRequest)
        async def create_user(data):
            return data

        assert create_user.__mitsuki_route__.produces_type == Response
        assert create_user.__mitsuki_route__.consumes_type == CreateRequest
