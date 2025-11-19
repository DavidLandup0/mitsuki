"""Tests for ResponseEntity automatic content type detection."""

from unittest.mock import Mock

import pytest
from starlette.requests import Request

from mitsuki.web.parameter_binder import ParameterBinder
from mitsuki.web.response import ResponseEntity
from mitsuki.web.response_processor import ResponseProcessor
from mitsuki.web.route_builder import RouteBuilder


class TestResponseEntityContentType:
    """Test automatic Content-Type detection based on response body."""

    @pytest.fixture
    def route_builder(self):
        """Create RouteBuilder instance."""
        mock_context = Mock()
        mock_context.controllers = []

        parameter_binder = ParameterBinder(
            max_body_size=1024 * 1024,
            max_file_size=10 * 1024 * 1024,
            max_request_size=20 * 1024 * 1024,
        )
        response_processor = ResponseProcessor()

        return RouteBuilder(
            context=mock_context,
            parameter_binder=parameter_binder,
            response_processor=response_processor,
            ignore_trailing_slash=False,
            debug_mode=False,
        )

    @pytest.mark.asyncio
    async def test_dict_returns_json(self, route_builder):
        """Should return application/json for dict."""

        async def handler():
            return ResponseEntity.ok({"message": "hello"})

        endpoint = route_builder._create_endpoint(handler, {}, None)
        mock_request = Mock(spec=Request)

        response = await endpoint(mock_request)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert b'"message"' in response.body and b'"hello"' in response.body

    @pytest.mark.asyncio
    async def test_list_returns_json(self, route_builder):
        """Should return application/json for list."""

        async def handler():
            return ResponseEntity.ok([1, 2, 3])

        endpoint = route_builder._create_endpoint(handler, {}, None)
        mock_request = Mock(spec=Request)

        response = await endpoint(mock_request)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert b"1" in response.body and b"2" in response.body and b"3" in response.body

    @pytest.mark.asyncio
    async def test_string_returns_text_plain(self, route_builder):
        """Should return text/plain for string."""

        async def handler():
            return ResponseEntity.ok("Hello, World!")

        endpoint = route_builder._create_endpoint(handler, {}, None)
        mock_request = Mock(spec=Request)

        response = await endpoint(mock_request)

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert response.body == b"Hello, World!"

    @pytest.mark.asyncio
    async def test_bytes_returns_octet_stream(self, route_builder):
        """Should return application/octet-stream for bytes."""

        async def handler():
            return ResponseEntity.ok(b"Binary data")

        endpoint = route_builder._create_endpoint(handler, {}, None)
        mock_request = Mock(spec=Request)

        response = await endpoint(mock_request)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert response.body == b"Binary data"

    @pytest.mark.asyncio
    async def test_none_returns_json(self, route_builder):
        """Should return application/json for None with empty body."""

        async def handler():
            return ResponseEntity.ok(None)

        endpoint = route_builder._create_endpoint(handler, {}, None)
        mock_request = Mock(spec=Request)

        response = await endpoint(mock_request)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.body == b""  # None results in empty body

    @pytest.mark.asyncio
    async def test_custom_content_type_xml(self, route_builder):
        """Should respect custom Content-Type header (XML)."""

        async def handler():
            xml_string = '<?xml version="1.0"?><root><message>Hello</message></root>'
            return ResponseEntity.ok(xml_string).header(
                "Content-Type", "application/xml"
            )

        endpoint = route_builder._create_endpoint(handler, {}, None)
        mock_request = Mock(spec=Request)

        response = await endpoint(mock_request)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        assert b"<?xml version" in response.body
        assert b"<message>Hello</message>" in response.body

    @pytest.mark.asyncio
    async def test_custom_content_type_csv(self, route_builder):
        """Should respect custom Content-Type header (CSV)."""

        async def handler():
            csv_data = "name,age\nAlice,25\nBob,30"
            return ResponseEntity.ok(csv_data).header("Content-Type", "text/csv")

        endpoint = route_builder._create_endpoint(handler, {}, None)
        mock_request = Mock(spec=Request)

        response = await endpoint(mock_request)

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"
        assert b"name,age" in response.body
        assert b"Alice,25" in response.body

    @pytest.mark.asyncio
    async def test_no_content_empty_body(self, route_builder):
        """Should return empty body for 204 No Content."""

        async def handler():
            return ResponseEntity.no_content()

        endpoint = route_builder._create_endpoint(handler, {}, None)
        mock_request = Mock(spec=Request)

        response = await endpoint(mock_request)

        assert response.status_code == 204
        assert response.body == b""

    @pytest.mark.asyncio
    async def test_custom_header_case_insensitive(self, route_builder):
        """Should respect Content-Type header regardless of case."""

        async def handler():
            # Use lowercase content-type
            return ResponseEntity.ok("Plain text").header("content-type", "text/plain")

        endpoint = route_builder._create_endpoint(handler, {}, None)
        mock_request = Mock(spec=Request)

        response = await endpoint(mock_request)

        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
