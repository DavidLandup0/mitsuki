import json
from typing import Any, Optional, get_origin

from starlette.requests import Request

from mitsuki.core.enums import ParameterKind
from mitsuki.exceptions import (
    FileTooLargeException,
    InvalidFileTypeException,
    RequestValidationException,
)
from mitsuki.web.multipart import parse_multipart
from mitsuki.web.response_processor import ResponseProcessor


class ParameterBinder:
    """Handles binding HTTP request data to handler parameters."""

    def __init__(self, max_body_size: int, max_file_size: int, max_request_size: int):
        self.max_body_size = max_body_size
        self.max_file_size = max_file_size
        self.max_request_size = max_request_size

    async def bind_parameters(
        self, request: Request, param_metadata: dict, route_meta: Any
    ) -> dict:
        """Build handler arguments from HTTP request."""
        args = {}
        path_params = request.path_params
        query_params = dict(request.query_params)

        for param_name, metadata in param_metadata.items():
            if metadata.kind == ParameterKind.REQUEST:
                args[param_name] = request
            elif metadata.kind == ParameterKind.PATH:
                args[param_name] = self._bind_path_param(
                    param_name, metadata, path_params
                )
            elif metadata.kind == ParameterKind.QUERY:
                args[param_name] = self._bind_query_param(
                    param_name, metadata, query_params
                )
            elif metadata.kind == ParameterKind.HEADER:
                args[param_name] = self._bind_header_param(
                    param_name, metadata, request
                )
            elif metadata.kind == ParameterKind.BODY:
                args[param_name] = await self._bind_body_param(
                    param_name, metadata, request, route_meta
                )
            elif metadata.kind == ParameterKind.FILE:
                args[param_name] = await self._bind_file_param(
                    param_name, metadata, request
                )
            elif metadata.kind == ParameterKind.FORM:
                args[param_name] = await self._bind_form_param(
                    param_name, metadata, request
                )
            elif metadata.kind == ParameterKind.AUTO:
                args[param_name] = self._bind_auto_param(
                    param_name, metadata, path_params, query_params
                )

        return args

    def _bind_path_param(
        self, param_name: str, metadata: Any, path_params: dict
    ) -> Any:
        """Bind path parameter."""
        value = path_params.get(metadata.name or param_name)
        if value is None and metadata.required:
            raise RequestValidationException(
                f"Required path parameter '{param_name}' not found"
            )
        if value is not None and metadata.param_type:
            value = self._coerce_type(value, metadata.param_type)
        return value

    def _bind_query_param(
        self, param_name: str, metadata: Any, query_params: dict
    ) -> Any:
        """Bind query parameter."""
        value = query_params.get(metadata.name or param_name, metadata.default)
        if value is None and metadata.required:
            raise RequestValidationException(
                f"Required query parameter '{param_name}' not found"
            )
        if value is not None and metadata.param_type:
            value = self._coerce_type(value, metadata.param_type)
        return value

    def _bind_header_param(
        self, param_name: str, metadata: Any, request: Request
    ) -> Any:
        """Bind header parameter."""
        header_name = (metadata.name or param_name).lower()
        value = request.headers.get(header_name, metadata.default)
        if value is None and metadata.required:
            raise RequestValidationException(
                f"Required header '{param_name}' not found"
            )
        return value

    async def _bind_body_param(
        self, param_name: str, metadata: Any, request: Request, route_meta: Any
    ) -> Any:
        """Bind body parameter."""
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            raise RequestValidationException(
                f"Request body too large (max {self.max_body_size} bytes)"
            )

        body_bytes = await request.body()

        if body_bytes:
            content_type = request.headers.get("content-type", "")
            if content_type and not content_type.startswith("application/json"):
                raise RequestValidationException(
                    f"Unsupported Content-Type: {content_type}. Expected application/json"
                )

        if body_bytes:
            try:
                body_data = json.loads(body_bytes)

                # Validate against consumes_type if specified
                consumes_type = route_meta.consumes_type if route_meta else None
                if consumes_type:
                    processor = ResponseProcessor()
                    body_data = processor.validate_and_convert_input(
                        body_data, consumes_type
                    )

                return body_data
            except json.JSONDecodeError as e:
                raise RequestValidationException(f"Invalid JSON in request body: {e}")
        elif metadata.required:
            raise RequestValidationException("Required request body not provided")

        return None

    async def _bind_file_param(
        self, param_name: str, metadata: Any, request: Request
    ) -> Any:
        """Bind file parameter."""
        form_data = await self._get_form_data(request)
        field_name = metadata.name or param_name

        # Check if expecting multiple files (List[UploadFile])
        if get_origin(metadata.param_type) is list:
            files = form_data.get_files(field_name)
            if not files and metadata.required:
                raise RequestValidationException(
                    f"Required file parameter '{param_name}' not found"
                )
            if files and metadata.allowed_types:
                self._validate_file_types(files, metadata.allowed_types, param_name)
            if files and metadata.max_size:
                self._validate_file_sizes(files, metadata.max_size)
            return files
        else:
            # Single file
            file = form_data.get_file(field_name)
            if not file and metadata.required:
                raise RequestValidationException(
                    f"Required file parameter '{param_name}' not found"
                )
            if file and metadata.allowed_types:
                self._validate_file_type(file, metadata.allowed_types, param_name)
            if file and metadata.max_size:
                self._validate_file_size(file, metadata.max_size)
            return file

    async def _bind_form_param(
        self, param_name: str, metadata: Any, request: Request
    ) -> Any:
        """Bind form parameter."""
        form_data = await self._get_form_data(request)
        field_name = metadata.name or param_name
        value = form_data.get_field(field_name)

        if value is None:
            value = metadata.default
        if value is None and metadata.required:
            raise RequestValidationException(
                f"Required form parameter '{param_name}' not found"
            )
        if value is not None and metadata.param_type:
            value = self._coerce_type(value, metadata.param_type)
        return value

    def _bind_auto_param(
        self, param_name: str, metadata: Any, path_params: dict, query_params: dict
    ) -> Optional[Any]:
        """Bind auto parameter (tries path first, then query)."""
        value = path_params.get(param_name) or query_params.get(param_name)
        if value is not None and metadata.param_type:
            value = self._coerce_type(value, metadata.param_type)
        return value

    async def _get_form_data(self, request: Request):
        """Get or parse multipart form data (cached in request state)."""
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            raise RequestValidationException("Expected multipart/form-data")

        if not hasattr(request.state, "form_data"):
            body_bytes = await request.body()
            request.state.form_data = await parse_multipart(
                content_type,
                body_bytes,
                max_file_size=self.max_file_size,
                max_request_size=self.max_request_size,
            )

        return request.state.form_data

    def _validate_file_types(
        self, files: list, allowed_types: list, param_name: str
    ) -> None:
        """Validate file types for multiple files."""
        for file in files:
            if file.content_type and file.content_type not in allowed_types:
                raise InvalidFileTypeException(
                    f"File type {file.content_type} not allowed for '{param_name}'. "
                    f"Allowed types: {allowed_types}"
                )

    def _validate_file_type(
        self, file: Any, allowed_types: list, param_name: str
    ) -> None:
        """Validate file type for single file."""
        if file.content_type and file.content_type not in allowed_types:
            raise InvalidFileTypeException(
                f"File type {file.content_type} not allowed for '{param_name}'. "
                f"Allowed types: {allowed_types}"
            )

    def _validate_file_sizes(self, files: list, max_size: int) -> None:
        """Validate file sizes for multiple files."""
        for file in files:
            if file.size > max_size:
                raise FileTooLargeException(
                    f"File {file.filename} exceeds maximum size {max_size} bytes"
                )

    def _validate_file_size(self, file: Any, max_size: int) -> None:
        """Validate file size for single file."""
        if file.size > max_size:
            raise FileTooLargeException(
                f"File {file.filename} exceeds maximum size {max_size} bytes"
            )

    def _coerce_type(self, value: Any, target_type: type) -> Any:
        """Coerce value to target type."""
        if value is None or isinstance(value, target_type):
            return value

        if target_type is str:
            return str(value)

        try:
            if target_type is int:
                return int(value)
            elif target_type is float:
                return float(value)
            elif target_type is bool:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    if value.lower() in ("true", "1", "yes"):
                        return True
                    elif value.lower() in ("false", "0", "no"):
                        return False
                raise RequestValidationException(f"Cannot convert '{value}' to bool")
            else:
                return target_type(value)
        except (ValueError, TypeError) as e:
            raise RequestValidationException(
                f"Cannot convert '{value}' to {target_type.__name__}: {e}"
            )
