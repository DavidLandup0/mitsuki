from typing import Any, Dict, Optional


class ResponseEntity:
    """
    Represents an HTTP response with body, status code, and headers.
    Similar to Spring Boot's ResponseEntity.

    Example:
        return ResponseEntity.ok({"message": "Success"})
        return ResponseEntity.created(user, headers={"Location": f"/api/users/{user.id}"})
        return ResponseEntity.status(418).body({"message": "I'm a teapot"})
        return ResponseEntity.not_found()
    """

    def __init__(
        self,
        body: Any = None,
        status: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.body = body
        self.status = status
        self.headers = headers or {}

    @classmethod
    def ok(cls, body: Any = None) -> "ResponseEntity":
        """Create a 200 OK response."""
        return cls(body=body, status=200)

    @classmethod
    def created(
        cls, body: Any = None, headers: Optional[Dict[str, str]] = None
    ) -> "ResponseEntity":
        """Create a 201 Created response."""
        return cls(body=body, status=201, headers=headers)

    @classmethod
    def accepted(cls, body: Any = None) -> "ResponseEntity":
        """Create a 202 Accepted response."""
        return cls(body=body, status=202)

    @classmethod
    def no_content(cls) -> "ResponseEntity":
        """Create a 204 No Content response."""
        return cls(body=None, status=204)

    @classmethod
    def bad_request(cls, body: Any = None) -> "ResponseEntity":
        """Create a 400 Bad Request response."""
        return cls(body=body, status=400)

    @classmethod
    def unauthorized(cls, body: Any = None) -> "ResponseEntity":
        """Create a 401 Unauthorized response."""
        return cls(body=body, status=401)

    @classmethod
    def forbidden(cls, body: Any = None) -> "ResponseEntity":
        """Create a 403 Forbidden response."""
        return cls(body=body, status=403)

    @classmethod
    def not_found(cls, body: Any = None) -> "ResponseEntity":
        """Create a 404 Not Found response."""
        return cls(body=body, status=404)

    @classmethod
    def conflict(cls, body: Any = None) -> "ResponseEntity":
        """Create a 409 Conflict response."""
        return cls(body=body, status=409)

    @classmethod
    def internal_server_error(cls, body: Any = None) -> "ResponseEntity":
        """Create a 500 Internal Server Error response."""
        return cls(body=body, status=500)

    @classmethod
    def status(cls, status_code: int) -> "ResponseEntityBuilder":
        """
        Create a response with a custom status code.
        Returns a builder for chaining.

        Example:
            return ResponseEntity.status(418).body({"message": "I'm a teapot"})
        """
        return ResponseEntityBuilder(status=status_code)

    def header(self, name: str, value: str) -> "ResponseEntity":
        """Add a header to the response."""
        self.headers[name] = value
        return self

    def to_tuple(self) -> tuple:
        """
        Convert to tuple format (body, status) for backward compatibility.
        Headers are currently not supported in tuple format.
        """
        return (self.body, self.status)


class ResponseEntityBuilder:
    """Builder for creating ResponseEntity with custom status codes."""

    def __init__(self, status: int):
        self.status = status
        self.headers: Dict[str, str] = {}

    def body(self, body: Any) -> ResponseEntity:
        """Set the response body and create the ResponseEntity."""
        return ResponseEntity(body=body, status=self.status, headers=self.headers)

    def header(self, name: str, value: str) -> "ResponseEntityBuilder":
        """Add a header to the response."""
        self.headers[name] = value
        return self

    def build(self) -> ResponseEntity:
        """Build the ResponseEntity without a body."""
        return ResponseEntity(body=None, status=self.status, headers=self.headers)


# Aliases for ResponseEntity
JsonResponse = ResponseEntity
JSONResponse = ResponseEntity
