"""
Tests for security features: request size limits, type coercion, error handling.
"""

from starlette.testclient import TestClient

from mitsuki import (
    GetMapping,
    PathVariable,
    PostMapping,
    QueryParam,
    RequestBody,
    RestController,
)
from mitsuki.config.properties import get_config
from mitsuki.core.container import DIContainer, set_container
from mitsuki.core.server import MitsukiASGIApp


class MockContext:
    """Mock application context for testing."""

    def __init__(self):
        self.controllers = []


class TestRequestSizeLimits:
    """Tests for request body size limits."""

    def setup_method(self):
        set_container(DIContainer())

        @RestController("/api")
        class TestController:
            @PostMapping("/upload")
            async def upload(self, data: dict = RequestBody()):
                return {"received": len(str(data))}

        context = MockContext()
        context.controllers = [(TestController, "/api")]
        self.app = MitsukiASGIApp(context)
        self.client = TestClient(self.app)

    def teardown_method(self):
        set_container(DIContainer())

    def test_request_within_size_limit(self):
        """Should accept requests within size limit."""
        data = {"message": "x" * 1000}  # ~1KB
        response = self.client.post("/api/upload", json=data)
        assert response.status_code == 200

    def test_request_exceeds_size_limit(self):
        """Should reject requests exceeding max body size."""
        # Default limit is 10MB, send something claiming to be larger
        large_data = "x" * (11 * 1024 * 1024)  # 11MB
        response = self.client.post(
            "/api/upload",
            content=large_data,
            headers={
                "Content-Length": str(len(large_data)),
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 400
        assert "too large" in response.json()["error"]


class TestTypeCoercion:
    """Tests for automatic type coercion of path and query parameters."""

    def setup_method(self):
        set_container(DIContainer())

        @RestController("/api")
        class TestController:
            @GetMapping("/users/{id}")
            async def get_user(self, id: int = PathVariable()):
                return {"id": id, "type": type(id).__name__}

            @GetMapping("/search")
            async def search(
                self,
                limit: int = QueryParam(default=10),
                active: bool = QueryParam(default=True),
                price: float = QueryParam(default=0.0),
            ):
                return {
                    "limit": limit,
                    "limit_type": type(limit).__name__,
                    "active": active,
                    "active_type": type(active).__name__,
                    "price": price,
                    "price_type": type(price).__name__,
                }

        context = MockContext()
        context.controllers = [(TestController, "/api")]
        self.app = MitsukiASGIApp(context)
        self.client = TestClient(self.app)

    def teardown_method(self):
        set_container(DIContainer())

    def test_path_param_coerced_to_int(self):
        """Should convert path parameter string to int."""
        response = self.client.get("/api/users/123")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 123
        assert data["type"] == "int"

    def test_query_param_coerced_to_int(self):
        """Should convert query parameter string to int."""
        response = self.client.get("/api/search?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["limit_type"] == "int"

    def test_query_param_coerced_to_bool_true(self):
        """Should convert query parameter string to bool (true)."""
        response = self.client.get("/api/search?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is True
        assert data["active_type"] == "bool"

    def test_query_param_coerced_to_bool_false(self):
        """Should convert query parameter string to bool (false)."""
        response = self.client.get("/api/search?active=false")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is False
        assert data["active_type"] == "bool"

    def test_query_param_coerced_to_float(self):
        """Should convert query parameter string to float."""
        response = self.client.get("/api/search?price=19.99")
        assert response.status_code == 200
        data = response.json()
        assert data["price"] == 19.99
        assert data["price_type"] == "float"

    def test_invalid_type_coercion_returns_400(self):
        """Should return 400 for invalid type conversion."""
        response = self.client.get("/api/users/abc")
        assert response.status_code == 400
        assert "Cannot convert" in response.json()["error"]


class TestErrorHandling:
    """Tests for error handling in debug vs production mode."""

    def test_production_mode_hides_error_details(self):
        """Should return generic error in production mode."""
        set_container(DIContainer())

        @RestController("/api")
        class TestController:
            @GetMapping("/error")
            async def trigger_error(self):
                raise RuntimeError("Something went wrong internally")

        context = MockContext()
        context.controllers = [(TestController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        # Default is debug=False (production)
        response = client.get("/api/error")
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "Internal server error"
        assert "RuntimeError" not in str(data)
        assert "Something went wrong" not in str(data)

        set_container(DIContainer())

    def test_debug_mode_shows_error_details(self, monkeypatch):
        """Should return detailed error in debug mode."""
        set_container(DIContainer())

        @RestController("/api")
        class TestController:
            @GetMapping("/error")
            async def trigger_error(self):
                raise RuntimeError("Something went wrong internally")

        context = MockContext()
        context.controllers = [(TestController, "/api")]

        config = get_config()
        original_get_bool = config.get_bool

        def mock_get_bool(key, default=None):
            if key == "debug":
                return True
            return original_get_bool(key, default)

        monkeypatch.setattr(config, "get_bool", mock_get_bool)

        app = MitsukiASGIApp(context)
        client = TestClient(app)

        response = client.get("/api/error")
        assert response.status_code == 500
        data = response.json()
        assert "Something went wrong internally" in data["error"]
        assert data["type"] == "RuntimeError"

        set_container(DIContainer())


class TestContentTypeValidation:
    """Tests for Content-Type validation on request bodies."""

    def setup_method(self):
        set_container(DIContainer())

        @RestController("/api")
        class TestController:
            @PostMapping("/data")
            async def post_data(self, data: dict = RequestBody()):
                return {"received": data}

        context = MockContext()
        context.controllers = [(TestController, "/api")]
        self.app = MitsukiASGIApp(context)
        self.client = TestClient(self.app)

    def teardown_method(self):
        set_container(DIContainer())

    def test_valid_json_content_type(self):
        """Should accept application/json content type."""
        response = self.client.post(
            "/api/data",
            json={"message": "hello"},
        )
        assert response.status_code == 200

    def test_invalid_content_type_rejected(self):
        """Should reject non-JSON content types."""
        response = self.client.post(
            "/api/data",
            content=b'{"message": "hello"}',
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 400
        assert "Unsupported Content-Type" in response.json()["error"]

    def test_xml_content_type_rejected(self):
        """Should reject XML content type."""
        response = self.client.post(
            "/api/data",
            content=b"<xml>data</xml>",
            headers={"Content-Type": "application/xml"},
        )
        assert response.status_code == 400
        assert "Unsupported Content-Type" in response.json()["error"]
