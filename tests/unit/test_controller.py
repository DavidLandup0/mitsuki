"""
Unit tests for @Controller, @RestController, and request mappings.
"""

import inspect

import pytest

from mitsuki import (
    Controller,
    DeleteMapping,
    GetMapping,
    PathVariable,
    PostMapping,
    PutMapping,
    QueryParam,
    RequestBody,
    RestController,
    RestRouter,
    Router,
    Service,
)
from mitsuki.core.container import DIContainer, get_container, set_container
from mitsuki.core.enums import StereotypeType


@pytest.fixture(autouse=True)
def reset_container():
    """Reset container before each test."""
    set_container(DIContainer())
    yield
    set_container(DIContainer())


class TestControllerRegistration:
    """Tests for @Controller and @RestController registration."""

    def test_controller_decorator(self):
        """@Controller should register controller."""

        @Controller("/api")
        class MyController:
            pass

        assert MyController._stereotype_subtype == StereotypeType.CONTROLLER
        assert MyController.__mitsuki_base_path__ == "/api"

    def test_rest_controller_decorator(self):
        """@RestController should register REST controller."""

        @RestController("/api/users")
        class UserController:
            pass

        assert UserController._stereotype_subtype == StereotypeType.CONTROLLER
        assert UserController.__mitsuki_base_path__ == "/api/users"

    def test_controller_without_path(self):
        """@Controller without path should default to empty string."""

        @Controller()
        class RootController:
            pass

        assert RootController.__mitsuki_base_path__ == ""

    def test_controller_in_registry(self):
        """Controllers should be registered in container."""

        @RestController("/api/test")
        class TestController:
            pass

        # Controller should be in the DI container
        container = get_container()
        assert TestController in container._components


class TestRequestMappings:
    """Tests for @GetMapping, @PostMapping, etc."""

    def test_get_mapping(self):
        """@GetMapping should register GET route."""

        @RestController("/api/users")
        class UserController:
            @GetMapping("/list")
            async def list_users(self):
                return []

        assert hasattr(UserController.list_users, "__mitsuki_route__")
        route_info = UserController.list_users.__mitsuki_route__
        assert route_info.method == "GET"
        assert route_info.path == "/list"

    def test_post_mapping(self):
        """@PostMapping should register POST route."""

        @RestController("/api/users")
        class UserController:
            @PostMapping("/create")
            async def create_user(self):
                return {}

        route_info = UserController.create_user.__mitsuki_route__
        assert route_info.method == "POST"
        assert route_info.path == "/create"

    def test_put_mapping(self):
        """@PutMapping should register PUT route."""

        @RestController("/api/users")
        class UserController:
            @PutMapping("/{id}")
            async def update_user(self, id: str):
                return {}

        route_info = UserController.update_user.__mitsuki_route__
        assert route_info.method == "PUT"
        assert route_info.path == "/{id}"

    def test_delete_mapping(self):
        """@DeleteMapping should register DELETE route."""

        @RestController("/api/users")
        class UserController:
            @DeleteMapping("/{id}")
            async def delete_user(self, id: str):
                return {}

        route_info = UserController.delete_user.__mitsuki_route__
        assert route_info.method == "DELETE"
        assert route_info.path == "/{id}"

    def test_mapping_without_path(self):
        """Mapping without path should default to /."""

        @RestController("/api/users")
        class UserController:
            @GetMapping()
            async def list_all(self):
                return []

        route_info = UserController.list_all.__mitsuki_route__
        assert route_info.path == ""


class TestParameterInjection:
    """Tests for parameter injection decorators."""

    def test_path_variable(self):
        """PathVariable should be instantiable."""

        @RestController("/api/users")
        class UserController:
            @GetMapping("/{id}")
            async def get_user(self, id: str = PathVariable()):
                return {"id": id}

        # Check that PathVariable is used as default
        sig = inspect.signature(UserController.get_user)
        default = sig.parameters["id"].default
        assert isinstance(default, PathVariable)

    def test_query_param(self):
        """QueryParam should be instantiable."""

        @RestController("/api/users")
        class UserController:
            @GetMapping("/search")
            async def search(self, q: str = QueryParam()):
                return {"query": q}

        sig = inspect.signature(UserController.search)
        default = sig.parameters["q"].default
        assert isinstance(default, QueryParam)

    def test_query_param_with_default(self):
        """@QueryParam should support default values."""

        @RestController("/api/users")
        class UserController:
            @GetMapping("/list")
            async def list_users(self, page: int = QueryParam(default=0)):
                return {"page": page}

        sig = inspect.signature(UserController.list_users)
        default = sig.parameters["page"].default
        assert default.default == 0

    def test_request_body(self):
        """RequestBody should be instantiable."""

        @RestController("/api/users")
        class UserController:
            @PostMapping("/create")
            async def create(self, user: dict = RequestBody()):
                return user

        sig = inspect.signature(UserController.create)
        default = sig.parameters["user"].default
        assert isinstance(default, RequestBody)


class TestControllerDependencyInjection:
    """Tests for dependency injection in controllers."""

    def test_controller_with_service_dependency(self):
        """Controllers should support constructor injection."""

        @Service()
        class UserService:
            def get_users(self):
                return ["user1", "user2"]

        @RestController("/api/users")
        class UserController:
            def __init__(self, service: UserService):
                self.service = service

            @GetMapping("/list")
            async def list_users(self):
                return self.service.get_users()

        container = get_container()

        controller = container.get(UserController)
        assert isinstance(controller.service, UserService)

    def test_controller_with_multiple_dependencies(self):
        """Controllers should support multiple dependencies."""

        @Service()
        class UserService:
            pass

        @Service()
        class AuthService:
            pass

        @RestController("/api")
        class ApiController:
            def __init__(self, user_service: UserService, auth_service: AuthService):
                self.user_service = user_service
                self.auth_service = auth_service

        container = get_container()

        controller = container.get(ApiController)
        assert isinstance(controller.user_service, UserService)
        assert isinstance(controller.auth_service, AuthService)


class TestMultipleRoutes:
    """Tests for controllers with multiple routes."""

    def test_controller_multiple_routes(self):
        """Controller can have multiple route handlers."""

        @RestController("/api/products")
        class ProductController:
            @GetMapping("/list")
            async def list_products(self):
                return []

            @GetMapping("/{id}")
            async def get_product(self, id: str = PathVariable()):
                return {"id": id}

            @PostMapping("/create")
            async def create_product(self, product: dict = RequestBody()):
                return product

            @DeleteMapping("/{id}")
            async def delete_product(self, id: str = PathVariable()):
                return {"deleted": True}

        assert hasattr(ProductController.list_products, "__mitsuki_route__")
        assert hasattr(ProductController.get_product, "__mitsuki_route__")
        assert hasattr(ProductController.create_product, "__mitsuki_route__")
        assert hasattr(ProductController.delete_product, "__mitsuki_route__")


class TestRouterAlias:
    """Tests for @Router as alias for @Controller."""

    def test_router_alias(self):
        """@Router should work as alias for @Controller."""

        @Router("/api/test")
        class TestRouter:
            @GetMapping("/hello")
            async def hello(self):
                return "world"

        assert TestRouter._stereotype_subtype == StereotypeType.CONTROLLER
        assert TestRouter.__mitsuki_base_path__ == "/api/test"

    def test_rest_router_alias(self):
        """@RestRouter should work as alias for @RestController."""

        @RestRouter("/api/items")
        class ItemRouter:
            @GetMapping("/all")
            async def get_all(self):
                return []

        assert ItemRouter._stereotype_subtype == StereotypeType.CONTROLLER
        assert ItemRouter.__mitsuki_base_path__ == "/api/items"
