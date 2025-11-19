"""
Tests for ResponseEntity and response processing.
"""

from mitsuki.web.response import JSONResponse, JsonResponse, ResponseEntity


class TestResponseEntity:
    """Tests for ResponseEntity class."""

    def test_ok(self):
        """Test 200 OK response."""
        response = ResponseEntity.ok({"message": "Success"})
        assert response.status == 200
        assert response.body == {"message": "Success"}
        assert response.headers == {}

    def test_created(self):
        """Test 201 Created response."""
        response = ResponseEntity.created({"id": 1, "name": "Test"})
        assert response.status == 201
        assert response.body == {"id": 1, "name": "Test"}

    def test_created_with_headers(self):
        """Test 201 Created with Location header."""
        response = ResponseEntity.created(
            {"id": 1}, headers={"Location": "/api/users/1"}
        )
        assert response.status == 201
        assert response.headers == {"Location": "/api/users/1"}

    def test_accepted(self):
        """Test 202 Accepted response."""
        response = ResponseEntity.accepted({"message": "Processing"})
        assert response.status == 202

    def test_no_content(self):
        """Test 204 No Content response."""
        response = ResponseEntity.no_content()
        assert response.status == 204
        assert response.body is None

    def test_bad_request(self):
        """Test 400 Bad Request response."""
        response = ResponseEntity.bad_request({"error": "Invalid input"})
        assert response.status == 400

    def test_unauthorized(self):
        """Test 401 Unauthorized response."""
        response = ResponseEntity.unauthorized({"error": "Not authenticated"})
        assert response.status == 401

    def test_forbidden(self):
        """Test 403 Forbidden response."""
        response = ResponseEntity.forbidden({"error": "Access denied"})
        assert response.status == 403

    def test_not_found(self):
        """Test 404 Not Found response."""
        response = ResponseEntity.not_found({"error": "Resource not found"})
        assert response.status == 404

    def test_conflict(self):
        """Test 409 Conflict response."""
        response = ResponseEntity.conflict({"error": "Email already exists"})
        assert response.status == 409

    def test_internal_server_error(self):
        """Test 500 Internal Server Error response."""
        response = ResponseEntity.internal_server_error({"error": "Server error"})
        assert response.status == 500

    def test_custom_status(self):
        """Test custom status code with builder."""
        response = ResponseEntity.status(418).body({"message": "I'm a teapot"})
        assert response.status == 418
        assert response.body == {"message": "I'm a teapot"}

    def test_custom_status_with_headers(self):
        """Test custom status with headers."""
        response = (
            ResponseEntity.status(503)
            .header("Retry-After", "300")
            .body({"error": "Service unavailable"})
        )
        assert response.status == 503
        assert response.headers == {"Retry-After": "300"}
        assert response.body == {"error": "Service unavailable"}

    def test_header_chaining(self):
        """Test adding multiple headers."""
        response = (
            ResponseEntity.ok({"data": "test"})
            .header("X-Custom", "value1")
            .header("Cache-Control", "max-age=3600")
        )
        assert response.headers == {
            "X-Custom": "value1",
            "Cache-Control": "max-age=3600",
        }

    def test_builder_without_body(self):
        """Test builder without body."""
        response = ResponseEntity.status(204).build()
        assert response.status == 204
        assert response.body is None

    def test_to_tuple(self):
        """Test conversion to tuple format."""
        response = ResponseEntity.created({"id": 1})
        data, status = response.to_tuple()
        assert status == 201
        assert data == {"id": 1}


class TestResponseEntityAliases:
    """Tests for ResponseEntity aliases."""

    def test_json_response_alias(self):
        """Test JsonResponse is same as ResponseEntity."""
        assert JsonResponse is ResponseEntity

    def test_json_response_ok(self):
        """Test JsonResponse.ok() works."""
        response = JsonResponse.ok({"message": "Success"})
        assert response.status == 200

    def test_jsonresponse_alias(self):
        """Test JSONResponse is same as ResponseEntity."""
        assert JSONResponse is ResponseEntity

    def test_jsonresponse_created(self):
        """Test JSONResponse.created() works."""
        response = JSONResponse.created({"id": 1})
        assert response.status == 201
