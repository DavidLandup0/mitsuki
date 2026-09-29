"""
Tests for response validation and field filtering.
"""

from dataclasses import dataclass

import msgspec
import pytest
from starlette.testclient import TestClient

from mitsuki import GetMapping, RestController
from mitsuki.core.container import DIContainer, set_container
from mitsuki.core.server import MitsukiASGIApp
from mitsuki.exceptions import RequestValidationException
from mitsuki.web.response_processor import ResponseProcessor


@dataclass
class UserDTO:
    """Test DTO for validation."""

    id: int
    name: str
    email: str


@dataclass
class PostDTO:
    """Test DTO with more fields."""

    id: int
    title: str
    content: str
    author_id: int
    views: int


@dataclass
class AccountDTO:
    """Dataclass carrying fields that must never reach a response."""

    id: int
    password: str
    api_key: str


class Account:
    """Plain object carrying fields that must never reach a response."""

    def __init__(self, id: int, password: str, api_key: str):
        self.id = id
        self.password = password
        self.api_key = api_key


class AccountStruct(msgspec.Struct):
    """msgspec Struct carrying fields that must never reach a response."""

    id: int
    password: str
    api_key: str


class MockContext:
    """Mock application context for testing."""

    def __init__(self):
        self.controllers = []


class TestExcludeFields:
    """Tests for field exclusion functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.processor = ResponseProcessor()

    def test_exclude_single_field_from_dict(self):
        """Test excluding a single field from dictionary."""
        data = {"id": 1, "name": "John", "password": "secret"}
        result = self.processor.exclude_fields(data, ["password"])
        assert result == {"id": 1, "name": "John"}
        assert "password" not in result

    def test_exclude_multiple_fields_from_dict(self):
        """Test excluding multiple fields from dictionary."""
        data = {"id": 1, "name": "John", "password": "secret", "internal_id": "xyz"}
        result = self.processor.exclude_fields(data, ["password", "internal_id"])
        assert result == {"id": 1, "name": "John"}

    def test_exclude_fields_from_list_of_dicts(self):
        """Test excluding fields from list of dictionaries."""
        data = [
            {"id": 1, "name": "John", "password": "secret1"},
            {"id": 2, "name": "Jane", "password": "secret2"},
        ]
        result = self.processor.exclude_fields(data, ["password"])
        assert len(result) == 2
        assert result[0] == {"id": 1, "name": "John"}
        assert result[1] == {"id": 2, "name": "Jane"}

    def test_exclude_fields_nested(self):
        """Test excluding fields from nested structures."""
        data = {
            "posts": [
                {"id": 1, "title": "Post 1", "author_id": 10, "views": 100},
                {"id": 2, "title": "Post 2", "author_id": 20, "views": 200},
            ],
            "count": 2,
        }
        result = self.processor.exclude_fields(data, ["author_id", "views"])
        assert result["count"] == 2
        assert len(result["posts"]) == 2
        assert result["posts"][0] == {"id": 1, "title": "Post 1"}
        assert result["posts"][1] == {"id": 2, "title": "Post 2"}

    def test_exclude_fields_deeply_nested(self):
        """Test excluding fields from deeply nested structures."""
        data = {
            "user": {
                "id": 1,
                "name": "John",
                "password": "secret",
                "profile": {"bio": "Developer", "internal_notes": "VIP"},
            }
        }
        result = self.processor.exclude_fields(data, ["password", "internal_notes"])
        assert "password" not in result["user"]
        assert result["user"]["profile"] == {"bio": "Developer"}

    def test_exclude_fields_with_none(self):
        """Test excluding fields when data is None."""
        result = self.processor.exclude_fields(None, ["field"])
        assert result is None

    def test_exclude_fields_empty_list(self):
        """Test with empty exclusion list."""
        data = {"id": 1, "name": "John"}
        result = self.processor.exclude_fields(data, [])
        assert result == data

    def test_exclude_nonexistent_field(self):
        """Test excluding a field that doesn't exist."""
        data = {"id": 1, "name": "John"}
        result = self.processor.exclude_fields(data, ["password"])
        assert result == data


class TestReturnTypeValidation:
    """Tests for return_type validation."""

    def setup_method(self):
        """Setup test fixtures."""
        self.processor = ResponseProcessor()

    def test_validate_dict_to_dataclass(self):
        """Test validating and converting dict to dataclass."""
        data = {"id": 1, "name": "John", "email": "john@example.com"}
        result = self.processor.validate_and_convert(data, UserDTO)
        assert result == {"id": 1, "name": "John", "email": "john@example.com"}

    def test_validate_dataclass_to_dict(self):
        """Test converting dataclass instance to dict."""
        user = UserDTO(id=1, name="John", email="john@example.com")
        result = self.processor.validate_and_convert(user, UserDTO)
        assert result == {"id": 1, "name": "John", "email": "john@example.com"}

    def test_validate_list_of_dicts(self):
        """Test validating list of dictionaries."""
        data = [
            {"id": 1, "name": "John", "email": "john@example.com"},
            {"id": 2, "name": "Jane", "email": "jane@example.com"},
        ]
        result = self.processor.validate_and_convert(data, UserDTO)
        assert len(result) == 2
        assert result[0] == {"id": 1, "name": "John", "email": "john@example.com"}
        assert result[1] == {"id": 2, "name": "Jane", "email": "jane@example.com"}

    def test_validate_list_of_dataclasses(self):
        """Test converting list of dataclass instances."""
        data = [
            UserDTO(id=1, name="John", email="john@example.com"),
            UserDTO(id=2, name="Jane", email="jane@example.com"),
        ]
        result = self.processor.validate_and_convert(data, UserDTO)
        assert len(result) == 2
        assert result[0] == {"id": 1, "name": "John", "email": "john@example.com"}

    def test_validation_failure_missing_field(self):
        """Test validation fails with missing required field."""
        data = {"id": 1, "name": "John"}  # Missing email
        with pytest.raises(RequestValidationException, match="Failed to validate"):
            self.processor.validate_and_convert(data, UserDTO)

    def test_validation_failure_wrong_type(self):
        """Test validation fails with wrong type."""
        data = "not a dict or dataclass"
        with pytest.raises(
            RequestValidationException, match="Response validation failed"
        ):
            self.processor.validate_and_convert(data, UserDTO)


class TestProcessResponseData:
    """Tests for complete response processing."""

    def setup_method(self):
        """Setup test fixtures."""
        self.processor = ResponseProcessor()

    def test_process_with_return_type_only(self):
        """Test processing with only return_type."""
        data = {"id": 1, "name": "John", "email": "john@example.com"}
        result = self.processor.process_response_data(data, UserDTO, [])
        assert result == {"id": 1, "name": "John", "email": "john@example.com"}

    def test_process_with_exclude_fields_only(self):
        """Test processing with only exclude_fields."""
        data = {"id": 1, "name": "John", "password": "secret"}
        result = self.processor.process_response_data(data, None, ["password"])
        assert result == {"id": 1, "name": "John"}

    def test_process_with_both_return_type_and_exclude(self):
        """Test processing with both return_type and exclude_fields."""
        post = PostDTO(id=1, title="Test", content="Content", author_id=10, views=100)
        result = self.processor.process_response_data(
            post, PostDTO, ["author_id", "views"]
        )
        assert result == {"id": 1, "title": "Test", "content": "Content"}

    def test_process_with_none_data(self):
        """Test processing None data."""
        result = self.processor.process_response_data(None, None, [])
        assert result is None

    def test_process_with_neither(self):
        """Test processing with neither return_type nor exclude_fields."""
        data = {"id": 1, "name": "John"}
        result = self.processor.process_response_data(data, None, [])
        assert result == data


class TestExcludeFieldsOnObjects:
    """Excluded fields must be removed from every shape the serializer encodes."""

    def setup_method(self):
        self.processor = ResponseProcessor()

    def test_exclude_fields_from_dataclass(self):
        result = self.processor.process_response_data(
            AccountDTO(id=1, password="secret", api_key="key"),
            None,
            ["password", "api_key"],
        )
        assert result == {"id": 1}

    def test_exclude_fields_from_plain_object(self):
        result = self.processor.process_response_data(
            Account(id=1, password="secret", api_key="key"),
            None,
            ["password", "api_key"],
        )
        assert result == {"id": 1}

    def test_exclude_fields_from_struct(self):
        result = self.processor.process_response_data(
            AccountStruct(id=1, password="secret", api_key="key"),
            None,
            ["password", "api_key"],
        )
        assert result == {"id": 1}

    def test_exclude_fields_from_objects_nested_in_containers(self):
        data = {
            "owner": Account(id=1, password="secret", api_key="key"),
            "members": [AccountDTO(id=2, password="secret", api_key="key")],
        }
        result = self.processor.process_response_data(
            data, None, ["password", "api_key"]
        )
        assert result == {"owner": {"id": 1}, "members": [{"id": 2}]}


class TestExcludeFieldsEndToEnd:
    """Excluded fields must not appear in the HTTP response body."""

    def setup_method(self):
        set_container(DIContainer())

    def teardown_method(self):
        set_container(DIContainer())

    def test_object_response_omits_excluded_fields(self):
        @RestController("/api")
        class AccountController:
            @GetMapping("/account", exclude_fields=["password", "api_key"])
            async def account(self) -> Account:
                return Account(id=1, password="secret", api_key="key")

        context = MockContext()
        context.controllers = [(AccountController, "/api")]
        client = TestClient(MitsukiASGIApp(context))

        response = client.get("/api/account")

        assert response.status_code == 200
        assert response.json() == {"id": 1}
