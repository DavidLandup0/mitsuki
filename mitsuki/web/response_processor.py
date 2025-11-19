from dataclasses import asdict, is_dataclass
from typing import Any, Optional

from mitsuki.exceptions import RequestValidationException


class ResponseProcessor:
    """Handles response data processing, validation, and transformation."""

    def process_response_data(
        self, data: Any, produces_type: Optional[type], exclude_fields: list
    ) -> Any:
        """Process response data with validation and field filtering."""
        if data is None:
            return None

        # Validate/convert to produces_type if specified
        if produces_type is not None:
            data = self.validate_and_convert(data, produces_type)

        # Apply field exclusion
        if exclude_fields:
            data = self.exclude_fields(data, exclude_fields)

        return data

    def validate_and_convert(self, data: Any, return_type: type) -> Any:
        """Validate and convert data to expected type (for output)."""

        # Handle lists
        if isinstance(data, list):
            return [self.validate_and_convert(item, return_type) for item in data]

        # If already correct type, return as-is
        if isinstance(data, return_type):
            # Convert dataclass to dict for JSON serialization
            if is_dataclass(data):
                return asdict(data)
            return data

        # If data is dict and return_type is a dataclass, try to construct it
        if isinstance(data, dict) and is_dataclass(return_type):
            try:
                instance = return_type(**data)
                return asdict(instance)
            except Exception as e:
                raise RequestValidationException(
                    f"Failed to validate response against {return_type.__name__}: {e}"
                )

        # Type mismatch - raise validation error
        raise RequestValidationException(
            f"Response validation failed: expected {return_type.__name__}, got {type(data).__name__}"
        )

    def validate_and_convert_input(self, data: Any, consumes_type: type) -> Any:
        """Validate and convert input data to expected type (for input)."""

        # Handle lists
        if isinstance(data, list):
            return [
                self.validate_and_convert_input(item, consumes_type) for item in data
            ]

        # If already correct type, return as-is
        if isinstance(data, consumes_type):
            return data

        # If data is dict and consumes_type is a dataclass, try to construct it
        if isinstance(data, dict) and is_dataclass(consumes_type):
            try:
                # Create dataclass instance and return it (not asdict)
                instance = consumes_type(**data)
                return instance
            except Exception as e:
                raise RequestValidationException(
                    f"Failed to validate input against {consumes_type.__name__}: {e}"
                )

        # Type mismatch - raise validation error
        raise RequestValidationException(
            f"Input validation failed: expected {consumes_type.__name__}, got {type(data).__name__}"
        )

    def exclude_fields(self, data: Any, exclude_fields: list) -> Any:
        """Remove specified fields from response data, recursively processing nested structures."""
        if data is None:
            return None

        # Handle lists
        if isinstance(data, list):
            return [self.exclude_fields(item, exclude_fields) for item in data]

        # Handle dicts
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if k not in exclude_fields:
                    # Recursively process nested structures
                    result[k] = self.exclude_fields(v, exclude_fields)
            return result

        # Return as-is for other types
        return data
