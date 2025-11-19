"""
Tests for @Produces and @Consumes decorators.
"""

from dataclasses import dataclass

import pytest

from mitsuki.exceptions import RequestValidationException
from mitsuki.web.mappings import Consumes, GetMapping, PostMapping, Produces
from mitsuki.web.response_processor import ResponseProcessor


@dataclass
class TestInputDTO:
    """Test input DTO."""

    name: str
    email: str
    age: int = 18


@dataclass
class TestOutputDTO:
    """Test output DTO."""

    id: int
    name: str
    email: str


class MockContext:
    """Mock application context for testing."""

    def __init__(self):
        self.controllers = []


class TestProducesDecorator:
    """Tests for @Produces decorator."""

    def test_produces_decorator_sets_metadata(self):
        """Test that @Produces decorator sets produces_type in metadata."""

        @Produces(TestOutputDTO)
        @GetMapping("/test")
        async def test_handler():
            return {"id": 1, "name": "John", "email": "john@example.com"}

        assert hasattr(test_handler, "__mitsuki_route__")
        assert test_handler.__mitsuki_route__.produces_type == TestOutputDTO

    def test_produces_with_type_parameter(self):
        """Test @Produces with explicit type parameter."""

        @Produces(type_or_dto=TestOutputDTO)
        @GetMapping("/test")
        async def test_handler():
            return {"id": 1, "name": "John", "email": "john@example.com"}

        assert test_handler.__mitsuki_route__.produces_type == TestOutputDTO

    def test_produces_decorator_before_mapping(self):
        """Test @Produces can be applied before @GetMapping."""

        @GetMapping("/test")
        @Produces(TestOutputDTO)
        async def test_handler():
            return {"id": 1, "name": "John", "email": "john@example.com"}

        assert test_handler.__mitsuki_route__.produces_type == TestOutputDTO

    def test_produces_integrates_with_return_type(self):
        """Test @Produces works alongside return_type parameter."""

        # When @Produces is applied after @GetMapping, it overrides return_type
        @Produces(TestOutputDTO)
        @GetMapping("/test", return_type=TestInputDTO)
        async def test_handler():
            return {"id": 1, "name": "John", "email": "john@example.com"}

        # @Produces applied last, so it overrides
        assert test_handler.__mitsuki_route__.produces_type == TestOutputDTO


class TestConsumesDecorator:
    """Tests for @Consumes decorator."""

    def test_consumes_decorator_sets_metadata(self):
        """Test that @Consumes decorator sets consumes_type in metadata."""

        @Consumes(TestInputDTO)
        @PostMapping("/test")
        async def test_handler(data):
            return data

        assert hasattr(test_handler, "__mitsuki_route__")
        assert test_handler.__mitsuki_route__.consumes_type == TestInputDTO

    def test_consumes_with_type_parameter(self):
        """Test @Consumes with explicit type parameter."""

        @Consumes(type_or_dto=TestInputDTO)
        @PostMapping("/test")
        async def test_handler(data):
            return data

        assert test_handler.__mitsuki_route__.consumes_type == TestInputDTO

    def test_consumes_decorator_before_mapping(self):
        """Test @Consumes can be applied before @PostMapping."""

        @PostMapping("/test")
        @Consumes(TestInputDTO)
        async def test_handler(data):
            return data

        assert test_handler.__mitsuki_route__.consumes_type == TestInputDTO


class TestProducesConsumesIntegration:
    """Tests for @Produces and @Consumes used together."""

    def test_both_decorators(self):
        """Test using both @Produces and @Consumes together."""

        @Produces(TestOutputDTO)
        @Consumes(TestInputDTO)
        @PostMapping("/test")
        async def test_handler(data):
            return {"id": 1, "name": data.name, "email": data.email}

        assert test_handler.__mitsuki_route__.produces_type == TestOutputDTO
        assert test_handler.__mitsuki_route__.consumes_type == TestInputDTO

    def test_decorators_different_order(self):
        """Test decorator order doesn't matter."""

        @Consumes(TestInputDTO)
        @Produces(TestOutputDTO)
        @PostMapping("/test")
        async def test_handler(data):
            return {"id": 1, "name": data.name, "email": data.email}

        assert test_handler.__mitsuki_route__.produces_type == TestOutputDTO
        assert test_handler.__mitsuki_route__.consumes_type == TestInputDTO


class TestInputValidation:
    """Tests for input validation with @Consumes."""

    def setup_method(self):
        """Setup test fixtures."""
        self.processor = ResponseProcessor()

    def test_validate_dict_to_dataclass_input(self):
        """Test validating dict input against dataclass."""
        data = {"name": "John", "email": "john@example.com", "age": 25}
        result = self.processor.validate_and_convert_input(data, TestInputDTO)

        assert isinstance(result, TestInputDTO)
        assert result.name == "John"
        assert result.email == "john@example.com"
        assert result.age == 25

    def test_validate_dict_to_dataclass_with_defaults(self):
        """Test validation uses default values from dataclass."""
        data = {"name": "John", "email": "john@example.com"}
        result = self.processor.validate_and_convert_input(data, TestInputDTO)

        assert isinstance(result, TestInputDTO)
        assert result.age == 18  # default value

    def test_validate_input_missing_required_field(self):
        """Test validation fails when required field is missing."""
        data = {"name": "John"}  # Missing required email field
        with pytest.raises(
            RequestValidationException, match="Failed to validate input"
        ):
            self.processor.validate_and_convert_input(data, TestInputDTO)

    def test_validate_input_list_of_dicts(self):
        """Test validating list of dictionaries."""
        data = [
            {"name": "John", "email": "john@example.com", "age": 25},
            {"name": "Jane", "email": "jane@example.com", "age": 30},
        ]
        result = self.processor.validate_and_convert_input(data, TestInputDTO)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, TestInputDTO) for item in result)
        assert result[0].name == "John"
        assert result[1].name == "Jane"

    def test_validate_input_wrong_type(self):
        """Test validation fails with wrong input type."""
        data = "not a dict"
        with pytest.raises(RequestValidationException, match="Input validation failed"):
            self.processor.validate_and_convert_input(data, TestInputDTO)


class TestOutputValidation:
    """Tests for output validation with @Produces."""

    def setup_method(self):
        """Setup test fixtures."""
        self.processor = ResponseProcessor()

    def test_output_validation_dict_to_dataclass(self):
        """Test output validation with dict."""
        data = {"id": 1, "name": "John", "email": "john@example.com"}
        result = self.processor.validate_and_convert(data, TestOutputDTO)

        # Output should be dict for JSON serialization
        assert isinstance(result, dict)
        assert result == {"id": 1, "name": "John", "email": "john@example.com"}

    def test_output_validation_dataclass_to_dict(self):
        """Test output validation with dataclass instance."""
        data = TestOutputDTO(id=1, name="John", email="john@example.com")
        result = self.processor.validate_and_convert(data, TestOutputDTO)

        # Should convert to dict for JSON serialization
        assert isinstance(result, dict)
        assert result == {"id": 1, "name": "John", "email": "john@example.com"}

    def test_output_validation_missing_field(self):
        """Test output validation fails with missing field."""
        data = {"id": 1, "name": "John"}  # Missing email
        with pytest.raises(
            RequestValidationException, match="Failed to validate response"
        ):
            self.processor.validate_and_convert(data, TestOutputDTO)


class TestMappingParameterIntegration:
    """Tests for produces_type/consumes_type as mapping parameters."""

    def test_produces_type_parameter(self):
        """Test produces_type parameter on @GetMapping."""

        @GetMapping("/test", produces_type=TestOutputDTO)
        async def test_handler():
            return {"id": 1, "name": "John", "email": "john@example.com"}

        assert test_handler.__mitsuki_route__.produces_type == TestOutputDTO

    def test_consumes_type_parameter(self):
        """Test consumes_type parameter on @PostMapping."""

        @PostMapping("/test", consumes_type=TestInputDTO)
        async def test_handler(data):
            return data

        assert test_handler.__mitsuki_route__.consumes_type == TestInputDTO

    def test_return_type_alias_for_produces_type(self):
        """Test return_type still works as alias for produces_type."""

        @GetMapping("/test", return_type=TestOutputDTO)
        async def test_handler():
            return {"id": 1, "name": "John", "email": "john@example.com"}

        assert test_handler.__mitsuki_route__.produces_type == TestOutputDTO

    def test_produces_type_takes_precedence_over_return_type(self):
        """Test produces_type parameter takes precedence over return_type."""

        @GetMapping("/test", produces_type=TestOutputDTO, return_type=TestInputDTO)
        async def test_handler():
            return {"id": 1, "name": "John", "email": "john@example.com"}

        assert test_handler.__mitsuki_route__.produces_type == TestOutputDTO
