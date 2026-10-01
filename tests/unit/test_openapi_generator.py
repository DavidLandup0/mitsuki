"""
Unit tests for OpenAPI specification generation and endpoint registration.
"""

from dataclasses import dataclass

import pytest

from mitsuki import GetMapping, PostMapping, RestController
from mitsuki.openapi import (
    OpenAPIOperation,
    UIType,
    generate_openapi_spec,
    register_openapi_endpoints,
)
from mitsuki.openapi.generator import _build_info, _build_servers
from mitsuki.openapi.schemas import clear_schema_registry


@dataclass
class User:
    """Response model."""

    id: int
    name: str


class FakeContext:
    """Minimal stand-in for ApplicationContext."""

    def __init__(self, controllers=None):
        self.controllers = controllers if controllers is not None else []


class FakeConfig:
    """Config stub backed by a flat dict of dot-notation keys."""

    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def get_bool(self, key, default=False):
        return bool(self.values.get(key, default))


@pytest.fixture(autouse=True)
def clean_registry():
    """The schema registry is module-level state; isolate every test."""
    clear_schema_registry()
    yield
    clear_schema_registry()


@pytest.fixture
def user_controller():
    """A controller with two routes used across the generator tests."""

    @RestController("/api")
    class UserController:
        @GetMapping("/users")
        @OpenAPIOperation(summary="List users")
        async def list_users(self) -> User:
            return User(id=1, name="Test")

        @PostMapping("/users")
        async def create_user(self) -> User:
            return User(id=1, name="Test")

    return UserController


class TestBuildInfo:
    """Tests for the info object builder."""

    def test_title_and_version(self):
        info = _build_info(
            FakeConfig({"openapi.title": "My API", "openapi.version": "2.0.0"})
        )

        assert info == {"title": "My API", "version": "2.0.0"}

    def test_description_included(self):
        info = _build_info(
            FakeConfig(
                {
                    "openapi.title": "My API",
                    "openapi.version": "1.0.0",
                    "openapi.description": "Does things",
                }
            )
        )

        assert info["description"] == "Does things"

    def test_empty_description_omitted(self):
        info = _build_info(
            FakeConfig(
                {
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.description": "",
                }
            )
        )

        assert "description" not in info

    def test_contact_name_only(self):
        info = _build_info(
            FakeConfig(
                {
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.contact.name": "Team",
                }
            )
        )

        assert info["contact"] == {"name": "Team"}

    def test_contact_with_email_and_url(self):
        info = _build_info(
            FakeConfig(
                {
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.contact.name": "Team",
                    "openapi.contact.email": "team@example.com",
                    "openapi.contact.url": "https://example.com",
                }
            )
        )

        assert info["contact"] == {
            "name": "Team",
            "email": "team@example.com",
            "url": "https://example.com",
        }

    def test_email_without_name_is_ignored(self):
        """contact is only created when a name is present."""

        info = _build_info(
            FakeConfig(
                {
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.contact.email": "team@example.com",
                }
            )
        )

        assert "contact" not in info

    def test_license_with_url(self):
        info = _build_info(
            FakeConfig(
                {
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.license.name": "MIT",
                    "openapi.license.url": "https://opensource.org/licenses/MIT",
                }
            )
        )

        assert info["license"] == {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        }

    def test_license_name_only(self):
        info = _build_info(
            FakeConfig(
                {
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.license.name": "MIT",
                }
            )
        )

        assert info["license"] == {"name": "MIT"}

    def test_license_url_without_name_is_ignored(self):
        info = _build_info(
            FakeConfig(
                {
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.license.url": "https://x",
                }
            )
        )

        assert "license" not in info

    def test_full_info(self):
        info = _build_info(
            FakeConfig(
                {
                    "openapi.title": "My API",
                    "openapi.version": "1.0.0",
                    "openapi.description": "Does things",
                    "openapi.contact.name": "Team",
                    "openapi.contact.email": "team@example.com",
                    "openapi.contact.url": "https://example.com",
                    "openapi.license.name": "MIT",
                    "openapi.license.url": "https://opensource.org/licenses/MIT",
                }
            )
        )

        assert set(info) == {"title", "version", "description", "contact", "license"}


class TestBuildServers:
    """Tests for the servers array builder."""

    def test_no_server_configured(self):
        assert _build_servers(FakeConfig()) == []

    def test_empty_url_omits_servers(self):
        assert _build_servers(FakeConfig({"openapi.server.url": ""})) == []

    def test_url_only(self):
        assert _build_servers(
            FakeConfig({"openapi.server.url": "https://api.example.com"})
        ) == [{"url": "https://api.example.com"}]

    def test_url_with_description(self):
        assert _build_servers(
            FakeConfig(
                {
                    "openapi.server.url": "https://api.example.com",
                    "openapi.server.description": "Production",
                }
            )
        ) == [{"url": "https://api.example.com", "description": "Production"}]

    def test_description_without_url_is_ignored(self):
        assert (
            _build_servers(FakeConfig({"openapi.server.description": "Production"}))
            == []
        )


class TestGenerateOpenAPISpec:
    """Tests for the top-level spec generator."""

    def test_version_and_empty_paths(self):
        spec = generate_openapi_spec(
            FakeContext(),
            FakeConfig({"openapi.title": "My API", "openapi.version": "1.0.0"}),
        )

        assert spec["openapi"] == "3.1.0"
        assert spec["info"] == {"title": "My API", "version": "1.0.0"}
        assert spec["paths"] == {}
        assert spec["components"]["schemas"] == {}

    def test_servers_included_when_configured(self):
        spec = generate_openapi_spec(
            FakeContext(),
            FakeConfig(
                {
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.server.url": "https://api.example.com",
                }
            ),
        )

        assert spec["servers"] == [{"url": "https://api.example.com"}]

    def test_servers_key_absent_when_unconfigured(self):
        spec = generate_openapi_spec(
            FakeContext(), FakeConfig({"openapi.title": "A", "openapi.version": "1"})
        )

        assert "servers" not in spec

    def test_paths_built_from_controllers(self, user_controller):
        spec = generate_openapi_spec(
            FakeContext([(user_controller, "/api")]),
            FakeConfig({"openapi.title": "A", "openapi.version": "1"}),
        )

        assert set(spec["paths"]) == {"/api/users"}
        assert set(spec["paths"]["/api/users"]) == {"get", "post"}

    def test_schemas_collected_from_response_types(self, user_controller):
        spec = generate_openapi_spec(
            FakeContext([(user_controller, "/api")]),
            FakeConfig({"openapi.title": "A", "openapi.version": "1"}),
        )

        assert "User" in spec["components"]["schemas"]
        assert spec["components"]["schemas"]["User"]["title"] == "User"

    def test_paths_from_multiple_controllers_merge(self):
        @RestController("/api")
        class UserController:
            @GetMapping("/users")
            async def list_users(self) -> User:
                return User(id=1, name="Test")

        @RestController("/api")
        class ItemController:
            @GetMapping("/items")
            async def list_items(self) -> User:
                return User(id=1, name="Test")

        spec = generate_openapi_spec(
            FakeContext([(UserController, "/api"), (ItemController, "/api")]),
            FakeConfig({"openapi.title": "A", "openapi.version": "1"}),
        )

        assert set(spec["paths"]) == {"/api/users", "/api/items"}

    def test_controllers_sharing_a_path_merge_operations(self):
        @RestController("/api")
        class UserController:
            @GetMapping("/users")
            async def list_users(self):
                return {}

        @RestController("")
        class HealthController:
            @GetMapping("/users")
            async def health(self):
                return {}

        spec = generate_openapi_spec(
            FakeContext([(UserController, "/api"), (HealthController, "")]),
            FakeConfig({"openapi.title": "A", "openapi.version": "1"}),
        )

        assert len(spec["paths"]["/api/users"]) == 1

    def test_registry_is_cleared_between_calls(self, user_controller):
        """A second generation must not inherit the first call's schemas."""

        config = FakeConfig({"openapi.title": "A", "openapi.version": "1"})
        context = FakeContext([(user_controller, "/api")])

        first = generate_openapi_spec(context, config)
        assert "User" in first["components"]["schemas"]

        second = generate_openapi_spec(FakeContext(), config)
        assert second["components"]["schemas"] == {}


class TestUIType:
    """Tests for the UI type enum."""

    def test_values(self):
        assert UIType.SWAGGER.value == "swagger"
        assert UIType.REDOC.value == "redoc"
        assert UIType.SCALAR.value == "scalar"

    def test_lookup_accepts_lowercase_value(self):
        assert UIType("redoc") == UIType.REDOC

    def test_lookup_is_case_sensitive(self):
        """Callers normalize with .lower() before constructing the enum."""

        with pytest.raises(ValueError):
            UIType("REDOC")

    def test_unknown_value_raises(self):
        with pytest.raises(ValueError):
            UIType("unknown")


class TestRegisterOpenAPIEndpoints:
    """Tests for endpoint registration."""

    def test_disabled_registers_nothing(self):
        context = FakeContext()

        register_openapi_endpoints(context, FakeConfig({"openapi.enabled": False}))

        assert context.controllers == []

    def test_spec_controller_registered_first(self):
        """The spec endpoint is registered before any UI endpoints."""

        context = FakeContext()

        register_openapi_endpoints(
            context,
            FakeConfig(
                {
                    "openapi.enabled": True,
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.docs_ui": "scalar",
                    "openapi.docs_url": "/docs",
                    "openapi.openapi_url": "/openapi.json",
                    "openapi.ui": ["swagger"],
                }
            ),
        )

        assert context.controllers[0][0].__name__ == "OpenAPIController"
        assert context.controllers[0][1] == ""

    def test_docs_ui_default_is_scalar(self):
        context = FakeContext()

        register_openapi_endpoints(
            context,
            FakeConfig(
                {
                    "openapi.enabled": True,
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.docs_ui": "scalar",
                    "openapi.docs_url": "/docs",
                    "openapi.openapi_url": "/openapi.json",
                    "openapi.ui": [],
                }
            ),
        )

        assert [c.__name__ for c, _ in context.controllers] == [
            "OpenAPIController",
            "ScalarController",
        ]

    def test_registers_docs_ui_controller(self):
        context = FakeContext()

        register_openapi_endpoints(
            context,
            FakeConfig(
                {
                    "openapi.enabled": True,
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.docs_ui": "swagger",
                    "openapi.docs_url": "/docs",
                    "openapi.openapi_url": "/openapi.json",
                    "openapi.ui": [],
                }
            ),
        )

        assert len(context.controllers) == 2

    def test_each_enabled_ui_gets_named_path(self):
        context = FakeContext()

        register_openapi_endpoints(
            context,
            FakeConfig(
                {
                    "openapi.enabled": True,
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.docs_ui": "scalar",
                    "openapi.docs_url": "/docs",
                    "openapi.openapi_url": "/openapi.json",
                    "openapi.ui": ["swagger", "redoc", "scalar"],
                }
            ),
        )

        # spec + docs + one controller per enabled UI
        assert len(context.controllers) == 5

    def test_ui_config_accepts_bare_string(self):
        context = FakeContext()

        register_openapi_endpoints(
            context,
            FakeConfig(
                {
                    "openapi.enabled": True,
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.docs_ui": "redoc",
                    "openapi.docs_url": "/docs",
                    "openapi.openapi_url": "/openapi.json",
                    "openapi.ui": "swagger",
                }
            ),
        )

        # spec + docs + the single string-named UI
        assert len(context.controllers) == 3

    def test_unknown_ui_names_are_skipped(self):
        context = FakeContext()

        register_openapi_endpoints(
            context,
            FakeConfig(
                {
                    "openapi.enabled": True,
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.docs_ui": "scalar",
                    "openapi.docs_url": "/docs",
                    "openapi.openapi_url": "/openapi.json",
                    "openapi.ui": ["swagger", "nope", "also-nope"],
                }
            ),
        )

        # spec + docs + swagger only
        assert len(context.controllers) == 3

    def test_unknown_docs_ui_registers_spec_and_uis_only(self):
        context = FakeContext()

        register_openapi_endpoints(
            context,
            FakeConfig(
                {
                    "openapi.enabled": True,
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.docs_ui": "nope",
                    "openapi.docs_url": "/docs",
                    "openapi.openapi_url": "/openapi.json",
                    "openapi.ui": ["swagger"],
                }
            ),
        )

        # spec + swagger; no /docs controller because the type was unknown
        assert len(context.controllers) == 2

    def test_docs_ui_uppercase_is_accepted(self):
        context = FakeContext()

        register_openapi_endpoints(
            context,
            FakeConfig(
                {
                    "openapi.enabled": True,
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.docs_ui": "SCALAR",
                    "openapi.docs_url": "/docs",
                    "openapi.openapi_url": "/openapi.json",
                    "openapi.ui": [],
                }
            ),
        )

        assert len(context.controllers) == 2

    def test_missing_docs_ui_registers_spec_only(self):
        context = FakeContext()

        register_openapi_endpoints(
            context,
            FakeConfig(
                {
                    "openapi.enabled": True,
                    "openapi.title": "A",
                    "openapi.version": "1",
                    "openapi.openapi_url": "/openapi.json",
                    "openapi.ui": [],
                }
            ),
        )

        assert len(context.controllers) == 1
