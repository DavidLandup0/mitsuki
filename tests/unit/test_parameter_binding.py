"""
Tests for HTTP request -> handler parameter binding.

Covers type coercion of path/query/header/form parameters and request body
validation, including typing constructs (Optional, List[...], Any) that are
not runtime classes.
"""

import uuid
from dataclasses import dataclass
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

from mitsuki import (
    FormFile,
    FormParam,
    GetMapping,
    PathVariable,
    PostMapping,
    QueryParam,
    RequestBody,
    RequestHeader,
    RestController,
)
from mitsuki.core.container import DIContainer, set_container
from mitsuki.core.server import MitsukiASGIApp
from mitsuki.exceptions import RequestValidationException
from mitsuki.web.parameter_binder import ParameterBinder
from mitsuki.web.params import extract_param_metadata
from mitsuki.web.upload import UploadFile


class MockContext:
    """Mock application context for testing."""

    def __init__(self):
        self.controllers = []


def build_client(controller_cls, prefix="/api", max_body_size=1024 * 1024):
    """Build a TestClient serving a single controller."""
    context = MockContext()
    context.controllers = [(controller_cls, prefix)]

    values = {
        "server.max_body_size": max_body_size,
        "server.multipart.max_file_size": 1024 * 1024,
        "server.multipart.max_request_size": 1024 * 1024,
        "server.cors.allowed_origins": "*",
    }
    flags = {
        "server.cors.enabled": False,
        "debug": False,
        "server.ignore_trailing_slash": True,
    }

    config = MagicMock()
    config.get.side_effect = lambda key, default=None: values.get(key, default)
    config.get_bool.side_effect = lambda key, default=None: flags.get(key, default)

    with patch("mitsuki.core.server.get_config", return_value=config):
        app = MitsukiASGIApp(context)

    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_container():
    set_container(DIContainer())
    yield
    set_container(DIContainer())


class TestOptionalCoercion:
    """Optional[T] hints must coerce to T, not be treated as a class."""

    def test_optional_int_query_param_coerces(self):
        @RestController("/api")
        class C:
            @GetMapping("/opt")
            async def opt(self, x: Optional[int] = QueryParam()) -> dict:
                return {"x": x, "type": type(x).__name__}

        response = build_client(C).get("/api/opt?x=5")

        assert response.status_code == 200
        assert response.json() == {"x": 5, "type": "int"}

    def test_optional_int_query_param_omitted_is_none(self):
        @RestController("/api")
        class C:
            @GetMapping("/opt")
            async def opt(self, x: Optional[int] = QueryParam()) -> dict:
                return {"x": x}

        response = build_client(C).get("/api/opt")

        assert response.status_code == 200
        assert response.json() == {"x": None}

    def test_optional_path_variable_coerces(self):
        @RestController("/api")
        class C:
            @GetMapping("/item/{item_id}")
            async def item(self, item_id: Optional[int] = PathVariable()) -> dict:
                return {"item_id": item_id, "type": type(item_id).__name__}

        response = build_client(C).get("/api/item/42")

        assert response.status_code == 200
        assert response.json() == {"item_id": 42, "type": "int"}


class TestAnyAndUnannotated:
    """Unannotated parameters resolve to Any and must pass through untouched."""

    def test_unannotated_query_param_with_default(self):
        @RestController("/api")
        class C:
            @GetMapping("/anyp")
            async def anyp(self, x=QueryParam(default="fallback")) -> dict:
                return {"x": x}

        response = build_client(C).get("/api/anyp?x=hello")

        assert response.status_code == 200
        assert response.json() == {"x": "hello"}

    def test_unannotated_query_param_uses_default(self):
        @RestController("/api")
        class C:
            @GetMapping("/anyp")
            async def anyp(self, x=QueryParam(default="fallback")) -> dict:
                return {"x": x}

        response = build_client(C).get("/api/anyp")

        assert response.status_code == 200
        assert response.json() == {"x": "fallback"}

    def test_explicit_any_annotation_passes_through(self):
        @RestController("/api")
        class C:
            @GetMapping("/anyp")
            async def anyp(self, x: Any = QueryParam()) -> dict:
                return {"x": x}

        response = build_client(C).get("/api/anyp?x=hello")

        assert response.status_code == 200
        assert response.json() == {"x": "hello"}


class TestListCoercion:
    """Repeated query params bind to List[T]; strings must not be char-split."""

    def test_repeated_query_param_collects_all_values(self):
        @RestController("/api")
        class C:
            @GetMapping("/lst")
            async def lst(self, tag: List[str] = QueryParam()) -> dict:
                return {"tag": tag}

        response = build_client(C).get("/api/lst?tag=a&tag=b")

        assert response.status_code == 200
        assert response.json() == {"tag": ["a", "b"]}

    def test_single_value_becomes_one_element_list(self):
        @RestController("/api")
        class C:
            @GetMapping("/lst")
            async def lst(self, tag: List[str] = QueryParam()) -> dict:
                return {"tag": tag}

        response = build_client(C).get("/api/lst?tag=ab")

        assert response.status_code == 200
        assert response.json() == {"tag": ["ab"]}

    def test_list_of_int_coerces_elements(self):
        @RestController("/api")
        class C:
            @GetMapping("/lst")
            async def lst(self, n: List[int] = QueryParam()) -> dict:
                return {"n": n}

        response = build_client(C).get("/api/lst?n=1&n=2&n=3")

        assert response.status_code == 200
        assert response.json() == {"n": [1, 2, 3]}

    def test_bare_list_does_not_split_string_into_characters(self):
        @RestController("/api")
        class C:
            @GetMapping("/lst")
            async def lst(self, tag: list = QueryParam()) -> dict:
                return {"tag": tag}

        response = build_client(C).get("/api/lst?tag=ab")

        assert response.status_code == 200
        assert response.json() == {"tag": ["ab"]}


class TestScalarCoercion:
    """Scalar coercion and its failure mode."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
        ],
    )
    def test_bool_query_param(self, raw, expected):
        @RestController("/api")
        class C:
            @GetMapping("/flag")
            async def flag(self, on: bool = QueryParam()) -> dict:
                return {"on": on}

        response = build_client(C).get(f"/api/flag?on={raw}")

        assert response.status_code == 200
        assert response.json() == {"on": expected}

    def test_float_query_param(self):
        @RestController("/api")
        class C:
            @GetMapping("/f")
            async def f(self, x: float = QueryParam()) -> dict:
                return {"x": x}

        response = build_client(C).get("/api/f?x=3.5")

        assert response.status_code == 200
        assert response.json() == {"x": 3.5}

    def test_uncoercible_int_returns_400_not_500(self):
        @RestController("/api")
        class C:
            @GetMapping("/n")
            async def n(self, x: int = QueryParam()) -> dict:
                return {"x": x}

        response = build_client(C).get("/api/n?x=notanint")

        assert response.status_code == 400

    def test_uncoercible_bool_returns_400_not_500(self):
        @RestController("/api")
        class C:
            @GetMapping("/flag")
            async def flag(self, on: bool = QueryParam()) -> dict:
                return {"on": on}

        response = build_client(C).get("/api/flag?on=maybe")

        assert response.status_code == 400


class TestFalsyValues:
    """Falsy values must survive binding rather than being treated as missing."""

    def test_zero_query_param_is_not_replaced_by_default(self):
        @RestController("/api")
        class C:
            @GetMapping("/z")
            async def z(self, count: int = QueryParam(default=99)) -> dict:
                return {"count": count}

        response = build_client(C).get("/api/z?count=0")

        assert response.status_code == 200
        assert response.json() == {"count": 0}

    def test_empty_string_auto_param_is_preserved(self):
        @RestController("/api")
        class C:
            @GetMapping("/e")
            async def e(self, name: str = "") -> dict:
                return {"name": name, "is_none": name is None}

        response = build_client(C).get("/api/e?name=")

        assert response.status_code == 200
        assert response.json() == {"name": "", "is_none": False}


def multipart_fields(pairs):
    """Build a multipart/form-data body, allowing repeated field names."""
    boundary = "testboundary"
    lines = []
    for name, value in pairs:
        lines += [
            f"--{boundary}",
            f'Content-Disposition: form-data; name="{name}"',
            "",
            value,
        ]
    lines += [f"--{boundary}--", ""]

    return (
        "\r\n".join(lines).encode(),
        {"content-type": f"multipart/form-data; boundary={boundary}"},
    )


class TestFormBinding:
    """Multipart form fields coerce like other string-sourced params."""

    def test_form_field_is_coerced_to_int(self):
        @RestController("/api")
        class C:
            @PostMapping("/f")
            async def f(self, age: int = FormParam()) -> dict:
                return {"age": age, "type": type(age).__name__}

        content, headers = multipart_fields([("age", "30")])
        response = build_client(C).post("/api/f", content=content, headers=headers)

        assert response.status_code == 200
        assert response.json() == {"age": 30, "type": "int"}

    def test_repeated_form_field_collects_all_values(self):
        @RestController("/api")
        class C:
            @PostMapping("/f")
            async def f(self, tag: List[str] = FormParam()) -> dict:
                return {"tag": tag}

        content, headers = multipart_fields([("tag", "a"), ("tag", "b")])
        response = build_client(C).post("/api/f", content=content, headers=headers)

        assert response.status_code == 200
        assert response.json() == {"tag": ["a", "b"]}

    def test_missing_required_form_field_returns_400(self):
        @RestController("/api")
        class C:
            @PostMapping("/f")
            async def f(self, name: str = FormParam()) -> dict:
                return {"name": name}

        content, headers = multipart_fields([("other", "x")])
        response = build_client(C).post("/api/f", content=content, headers=headers)

        assert response.status_code == 400


class TestHeaderBinding:
    """Header parameters must coerce like other string-sourced params."""

    def test_header_is_coerced_to_int(self):
        @RestController("/api")
        class C:
            @GetMapping("/h")
            async def h(
                self, page: int = RequestHeader(name="X-Page", required=False)
            ) -> dict:
                return {"page": page, "type": type(page).__name__}

        response = build_client(C).get("/api/h", headers={"X-Page": "7"})

        assert response.status_code == 200
        assert response.json() == {"page": 7, "type": "int"}

    def test_missing_required_header_returns_400(self):
        @RestController("/api")
        class C:
            @GetMapping("/h")
            async def h(self, token: str = RequestHeader(name="X-Token")) -> dict:
                return {"token": token}

        response = build_client(C).get("/api/h")

        assert response.status_code == 400


@dataclass
class Address:
    city: str
    zipcode: str


@dataclass
class Person:
    name: str
    age: int
    address: Optional[Address] = None


class TestBodyBinding:
    """Request body decoding and validation."""

    def test_body_validates_into_dataclass(self):
        @RestController("/api")
        class C:
            @PostMapping("/p")
            async def p(self, person: Person = RequestBody()) -> dict:
                return {"name": person.name, "age": person.age}

        response = build_client(C).post("/api/p", json={"name": "Ada", "age": 36})

        assert response.status_code == 200
        assert response.json() == {"name": "Ada", "age": 36}

    def test_body_validates_nested_dataclass(self):
        @RestController("/api")
        class C:
            @PostMapping("/p")
            async def p(self, person: Person = RequestBody()) -> dict:
                return {"city": person.address.city}

        response = build_client(C).post(
            "/api/p",
            json={
                "name": "Ada",
                "age": 36,
                "address": {"city": "London", "zipcode": "E1"},
            },
        )

        assert response.status_code == 200
        assert response.json() == {"city": "London"}

    def test_body_with_wrong_field_type_returns_400(self):
        @RestController("/api")
        class C:
            @PostMapping("/p")
            async def p(self, person: Person = RequestBody()) -> dict:
                return {"age": person.age}

        response = build_client(C).post(
            "/api/p", json={"name": "Ada", "age": "not a number"}
        )

        assert response.status_code == 400

    def test_body_missing_required_field_returns_400(self):
        @RestController("/api")
        class C:
            @PostMapping("/p")
            async def p(self, person: Person = RequestBody()) -> dict:
                return {"name": person.name}

        response = build_client(C).post("/api/p", json={"name": "Ada"})

        assert response.status_code == 400

    def test_malformed_json_returns_400(self):
        @RestController("/api")
        class C:
            @PostMapping("/p")
            async def p(self, person: Person = RequestBody()) -> dict:
                return {"name": person.name}

        response = build_client(C).post(
            "/api/p",
            content=b"{not json",
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 400

    def test_json_suffix_content_type_is_accepted(self):
        @RestController("/api")
        class C:
            @PostMapping("/p")
            async def p(self, payload: dict = RequestBody()) -> dict:
                return payload

        response = build_client(C).post(
            "/api/p",
            content=b'{"a": 1}',
            headers={"content-type": "application/merge-patch+json"},
        )

        assert response.status_code == 200
        assert response.json() == {"a": 1}


class TestBodyValidationSemantics:
    """Documented validation behaviour for request bodies (docs/10)."""

    def build_client(self):
        @RestController("/api")
        class C:
            @PostMapping("/p")
            async def p(self, person: Person = RequestBody()) -> dict:
                return {
                    "name": person.name,
                    "age": person.age,
                    "age_type": type(person.age).__name__,
                    "city": person.address.city if person.address else None,
                    "address_type": type(person.address).__name__,
                }

        return build_client(C)

    def test_field_types_are_enforced(self):
        """A wrong-typed field is rejected rather than passed through."""
        response = self.build_client().post(
            "/api/p", json={"name": "Ada", "age": "not a number"}
        )

        assert response.status_code == 400

    def test_values_are_coerced_where_possible(self):
        """A numeric string for an int field arrives as an int."""
        response = self.build_client().post("/api/p", json={"name": "Ada", "age": "25"})

        assert response.status_code == 200
        assert response.json()["age"] == 25
        assert response.json()["age_type"] == "int"

    def test_nested_dataclass_is_constructed(self):
        """A nested field arrives as its declared type, not a dict."""
        response = self.build_client().post(
            "/api/p",
            json={
                "name": "Ada",
                "age": 36,
                "address": {"city": "London", "zipcode": "E1"},
            },
        )

        assert response.status_code == 200
        assert response.json()["city"] == "London"
        assert response.json()["address_type"] == "Address"

    def test_unknown_fields_are_ignored(self):
        """Fields the target type does not declare are dropped, not rejected."""
        response = self.build_client().post(
            "/api/p", json={"name": "Ada", "age": 36, "unexpected": "value"}
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Ada"

    def test_misspelled_field_leaves_target_at_default(self):
        """The consequence of ignoring unknown fields: typos pass silently."""
        response = self.build_client().post(
            "/api/p", json={"name": "Ada", "age": 36, "adress": {"city": "London"}}
        )

        assert response.status_code == 200
        assert response.json()["city"] is None


class TestBodySizeLimits:
    """Body size limits must hold regardless of Content-Length."""

    def test_oversized_body_with_content_length_rejected(self):
        @RestController("/api")
        class C:
            @PostMapping("/p")
            async def p(self, payload: dict = RequestBody()) -> dict:
                return {"ok": True}

        client = build_client(C, max_body_size=100)

        response = client.post("/api/p", json={"data": "x" * 500})

        assert response.status_code == 400

    def test_oversized_chunked_body_rejected(self):
        """No Content-Length header - limit must still be enforced."""

        @RestController("/api")
        class C:
            @PostMapping("/p")
            async def p(self, payload: dict = RequestBody()) -> dict:
                return {"ok": True}

        client = build_client(C, max_body_size=100)

        def chunks():
            yield b'{"data": "'
            yield b"x" * 500
            yield b'"}'

        response = client.post(
            "/api/p",
            content=chunks(),
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 400


class TestMultipartSizeLimits:
    """Multipart bodies must be capped while they are read, not after."""

    def test_oversized_multipart_rejected(self):
        @RestController("/api")
        class C:
            @PostMapping("/upload")
            async def upload(self, file: UploadFile = FormFile()) -> dict:
                return {"size": file.size}

        client = build_client(C)

        response = client.post(
            "/api/upload",
            files={"file": ("big.bin", b"x" * (2 * 1024 * 1024), "text/plain")},
        )

        assert response.status_code == 400
        assert "too large" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_multipart_stream_stops_at_limit(self):
        """Without Content-Length, reading must stop once the limit is crossed."""

        async def upload(file: UploadFile = FormFile()):
            pass

        chunk_size = 1024
        max_request_size = 10 * chunk_size
        plan = ParameterBinder(
            max_body_size=max_request_size,
            max_file_size=max_request_size,
            max_request_size=max_request_size,
        ).build_plan(extract_param_metadata(upload), None)

        chunks_available = 1000
        chunks_sent = 0

        async def receive():
            nonlocal chunks_sent
            chunks_sent += 1
            return {
                "type": "http.request",
                "body": b"x" * chunk_size,
                "more_body": chunks_sent < chunks_available,
            }

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/upload",
            "query_string": b"",
            "headers": [(b"content-type", b"multipart/form-data; boundary=b")],
        }

        with pytest.raises(RequestValidationException, match="too large"):
            await plan.bind(Request(scope, receive))

        assert chunks_sent <= max_request_size // chunk_size + 1


class TestPathVariableBinding:
    """Variables in the route path bind from the URL, whatever their type."""

    def test_complex_path_variable_ignores_body(self):
        @RestController("/api")
        class C:
            @PostMapping("/users/{user_id}")
            async def update(self, user_id: uuid.UUID) -> dict:
                return {"user_id": str(user_id)}

        url_id, body_id = uuid.uuid4(), uuid.uuid4()
        response = build_client(C).post(f"/api/users/{url_id}", json=str(body_id))

        assert response.status_code == 200
        assert response.json() == {"user_id": str(url_id)}

    def test_complex_path_variable_on_get(self):
        @RestController("/api")
        class C:
            @GetMapping("/users/{user_id}")
            async def get(self, user_id: uuid.UUID) -> dict:
                return {"user_id": str(user_id)}

        url_id = uuid.uuid4()
        response = build_client(C).get(f"/api/users/{url_id}")

        assert response.status_code == 200
        assert response.json() == {"user_id": str(url_id)}

    def test_complex_path_variable_in_controller_path(self):
        @RestController("/orgs/{org_id}")
        class C:
            @GetMapping("/members")
            async def members(self, org_id: uuid.UUID) -> dict:
                return {"org_id": str(org_id)}

        org_id = uuid.uuid4()
        response = build_client(C, prefix="/orgs/{org_id}").get(
            f"/orgs/{org_id}/members"
        )

        assert response.status_code == 200
        assert response.json() == {"org_id": str(org_id)}


class TestContentLengthHeader:
    """A malformed Content-Length header does not leak parser errors."""

    def test_non_numeric_content_length(self):
        @RestController("/api")
        class C:
            @PostMapping("/echo")
            async def echo(self, payload: dict = RequestBody()) -> dict:
                return payload

        response = build_client(C).post(
            "/api/echo",
            content=b'{"a": 1}',
            headers={"content-type": "application/json", "content-length": "abc"},
        )

        assert "invalid literal" not in response.text
        assert response.json() == {"a": 1}
