"""
Unit tests for the OpenAPI documentation UI controllers.
"""

import pytest
from starlette.testclient import TestClient

from mitsuki.core.container import DIContainer, set_container
from mitsuki.core.server import MitsukiASGIApp
from mitsuki.openapi.ui import (
    create_openapi_controller,
    create_redoc_controller,
    create_scalar_controller,
    create_swagger_ui_controller,
)


@pytest.fixture(autouse=True)
def reset_container():
    """Isolate the DI container each test builds its app with."""
    set_container(DIContainer())
    yield
    set_container(DIContainer())


class MockContext:
    """Minimal stand-in for ApplicationContext."""

    def __init__(self, controllers):
        self.controllers = controllers


def build_client(controller, base_path=""):
    """Serve a single generated controller over HTTP."""
    return TestClient(MitsukiASGIApp(MockContext([(controller, base_path)])))


class TestSwaggerUIController:
    """Tests for the Swagger UI controller."""

    def test_serves_html(self):
        client = build_client(create_swagger_ui_controller("/docs", "/openapi.json"))

        response = client.get("/docs")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "swagger-ui" in response.text

    def test_points_at_spec_url(self):
        client = build_client(create_swagger_ui_controller("/docs", "/openapi.json"))

        assert "/openapi.json" in client.get("/docs").text

    def test_custom_docs_path(self):
        client = build_client(create_swagger_ui_controller("/reference", "/spec.json"))

        assert client.get("/reference").status_code == 200

    def test_route_metadata(self):
        controller = create_swagger_ui_controller("/docs", "/openapi.json")

        assert controller.__name__ == "SwaggerUIController"
        assert controller.swagger_ui.__mitsuki_route__.method == "GET"
        assert controller.swagger_ui.__mitsuki_route__.path == "/docs"


class TestRedocController:
    """Tests for the ReDoc UI controller."""

    def test_serves_html(self):
        client = build_client(create_redoc_controller("/redoc", "/openapi.json"))

        response = client.get("/redoc")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "<redoc" in response.text

    def test_points_at_spec_url(self):
        client = build_client(create_redoc_controller("/redoc", "/openapi.json"))

        assert "/openapi.json" in client.get("/redoc").text

    def test_route_metadata(self):
        controller = create_redoc_controller("/redoc", "/openapi.json")

        assert controller.__name__ == "ReDocController"
        assert controller.redoc_ui.__mitsuki_route__.method == "GET"
        assert controller.redoc_ui.__mitsuki_route__.path == "/redoc"


class TestScalarController:
    """Tests for the Scalar UI controller."""

    def test_serves_html(self):
        client = build_client(create_scalar_controller("/scalar", "/openapi.json"))

        response = client.get("/scalar")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "api-reference" in response.text

    def test_points_at_spec_url(self):
        client = build_client(create_scalar_controller("/scalar", "/openapi.json"))

        assert "/openapi.json" in client.get("/scalar").text

    def test_route_metadata(self):
        controller = create_scalar_controller("/scalar", "/openapi.json")

        assert controller.__name__ == "ScalarController"
        assert controller.scalar_ui.__mitsuki_route__.method == "GET"
        assert controller.scalar_ui.__mitsuki_route__.path == "/scalar"


class TestOpenAPIController:
    """Tests for the spec controller."""

    def test_serves_spec_as_json(self):
        spec = {"openapi": "3.1.0", "info": {"title": "A", "version": "1"}}
        client = build_client(create_openapi_controller(spec, "/openapi.json"))

        response = client.get("/openapi.json")

        assert response.status_code == 200
        assert response.json() == spec

    def test_custom_spec_path(self):
        client = build_client(
            create_openapi_controller({"openapi": "3.1.0"}, "/spec.json")
        )

        assert client.get("/spec.json").status_code == 200

    def test_empty_spec_served_verbatim(self):
        client = build_client(create_openapi_controller({}, "/openapi.json"))

        assert client.get("/openapi.json").json() == {}

    def test_instance_exposes_spec(self):
        spec = {"openapi": "3.1.0"}

        assert create_openapi_controller(spec, "/openapi.json")().spec == spec

    def test_route_metadata(self):
        controller = create_openapi_controller({"openapi": "3.1.0"}, "/openapi.json")

        assert controller.__name__ == "OpenAPIController"
        assert controller.openapi_spec.__mitsuki_route__.method == "GET"
        assert controller.openapi_spec.__mitsuki_route__.path == "/openapi.json"


class TestGeneratedUIsTogether:
    """Tests for the full documentation surface registered at once."""

    def test_all_uis_and_spec_are_reachable(self):
        context = MockContext(
            [
                (create_openapi_controller({"openapi": "3.1.0"}, "/openapi.json"), ""),
                (create_swagger_ui_controller("/swagger", "/openapi.json"), ""),
                (create_redoc_controller("/redoc", "/openapi.json"), ""),
                (create_scalar_controller("/scalar", "/openapi.json"), ""),
            ]
        )
        client = TestClient(MitsukiASGIApp(context))

        assert client.get("/openapi.json").status_code == 200
        assert client.get("/swagger").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/scalar").status_code == 200

    def test_each_ui_has_a_distinct_path(self):
        """Registering three UIs at the same path would shadow each other."""

        context = MockContext(
            [
                (create_swagger_ui_controller("/docs", "/openapi.json"), ""),
                (create_redoc_controller("/docs", "/openapi.json"), ""),
                (create_scalar_controller("/docs", "/openapi.json"), ""),
            ]
        )
        client = TestClient(MitsukiASGIApp(context))

        body = client.get("/docs").text

        assert "swagger-ui" in body
