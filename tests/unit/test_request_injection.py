import pytest
from starlette.requests import Request

from mitsuki import GetMapping, PostMapping, QueryParam, RestController
from mitsuki.core.container import DIContainer, set_container
from mitsuki.web.params import extract_param_metadata


@pytest.fixture(autouse=True)
def reset_container():
    """Reset container before each test."""
    set_container(DIContainer())
    yield
    set_container(DIContainer())


class TestRequestInjection:
    """Tests for automatic Request injection based on type annotation."""

    def test_request_injection_in_get_handler(self):
        """Request should be injected when parameter is typed as Request."""

        @RestController("/api")
        class TestController:
            @GetMapping("/test")
            async def test_handler(self, request: Request) -> dict:
                return {"client_host": request.client.host}

        metadata = extract_param_metadata(TestController.test_handler)
        assert "request" in metadata
        assert metadata["request"].kind == "request"
        assert metadata["request"].param_type is Request

    def test_request_injection_with_other_params(self):
        """Request injection should work alongside other parameter types."""

        @RestController("/api")
        class TestController:
            @GetMapping("/users/{user_id}")
            async def get_user(
                self, request: Request, user_id: int, page: int = QueryParam(default=1)
            ) -> dict:
                return {
                    "user_id": user_id,
                    "page": page,
                    "client": request.client.host,
                }

        metadata = extract_param_metadata(TestController.get_user)
        assert "request" in metadata
        assert "user_id" in metadata
        assert "page" in metadata
        assert metadata["request"].kind == "request"
        assert metadata["user_id"].kind == "auto"
        assert metadata["page"].kind == "query"

    def test_request_injection_in_post_handler(self):
        """Request should be injected in POST handlers too."""

        @RestController("/api")
        class TestController:
            @PostMapping("/users")
            async def create_user(self, request: Request, data: dict) -> dict:
                return {"ip": request.client.host, "data": data}

        metadata = extract_param_metadata(TestController.create_user)
        assert "request" in metadata
        assert "data" in metadata
        assert metadata["request"].kind == "request"
        assert metadata["data"].kind == "body"

    def test_handler_without_request(self):
        @RestController("/api")
        class TestController:
            @GetMapping("/test")
            async def test_handler(self) -> dict:
                return {"status": "ok"}

        metadata = extract_param_metadata(TestController.test_handler)
        assert "request" not in metadata
        assert len(metadata) == 0
