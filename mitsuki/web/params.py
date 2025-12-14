import inspect
from dataclasses import dataclass
from typing import Any, Optional, get_origin, get_type_hints

from starlette.requests import Request


@dataclass
class ParamMetadata:
    """Metadata for parameter injection."""

    kind: str  # 'path', 'query', 'body', 'header', 'file', 'form', 'request'
    name: Optional[str] = None
    required: bool = True
    default: Any = None
    param_type: Optional[type] = None  # Type hint for type coercion
    max_size: Optional[int] = None  # For file uploads
    allowed_types: Optional[list] = None  # For file uploads


class PathVariable:
    """
    Marks a parameter as a path variable.

    Usage:
        @GetMapping("/users/{id}")
        async def get_user(self, id: int):
            ...
    """

    def __init__(self, name: Optional[str] = None, required: bool = True):
        self.name = name
        self.required = required

    def __repr__(self):
        return f"PathVariable(name={self.name}, required={self.required})"


class QueryParam:
    """
    Marks a parameter as a query parameter.

    Usage:
        @GetMapping("/users")
        async def list_users(self, page: int = QueryParam(default=1)):
            ...
    """

    def __init__(
        self, name: Optional[str] = None, required: bool = False, default: Any = None
    ):
        self.name = name
        self.required = required
        self.default = default

    def __repr__(self):
        return f"QueryParam(name={self.name}, required={self.required}, default={self.default})"


class RequestParam:
    """
    Alias for QueryParam (Spring compatibility).
    """

    def __init__(
        self, name: Optional[str] = None, required: bool = False, default: Any = None
    ):
        self.name = name
        self.required = required
        self.default = default

    def __repr__(self):
        return f"RequestParam(name={self.name}, required={self.required}, default={self.default})"


class RequestBody:
    """
    Marks a parameter as the request body (automatically parsed from JSON).

    Usage:
        @PostMapping("/users")
        async def create_user(self, user: User):
            ...
    """

    def __init__(self, required: bool = True):
        self.required = required

    def __repr__(self):
        return f"RequestBody(required={self.required})"


class RequestHeader:
    """
    Marks a parameter as a request header.

    Usage:
        @GetMapping("/profile")
        async def get_profile(self, authorization: str = RequestHeader(name="Authorization")):
            ...
    """

    def __init__(
        self, name: Optional[str] = None, required: bool = True, default: Any = None
    ):
        self.name = name
        self.required = required
        self.default = default

    def __repr__(self):
        return f"RequestHeader(name={self.name}, required={self.required}, default={self.default})"


class FormFile:
    """
    Marks a parameter as an uploaded file from multipart/form-data.

    Usage:
        @PostMapping("/upload")
        async def upload(self, file: UploadFile = FormFile()):
            ...

        @PostMapping("/upload/multiple")
        async def upload_many(self, files: List[UploadFile] = FormFile()):
            ...

        @PostMapping("/upload/optional")
        async def upload_optional(self, file: Optional[UploadFile] = FormFile(required=False)):
            ...
    """

    def __init__(
        self,
        name: Optional[str] = None,
        required: bool = True,
        max_size: Optional[int] = None,
        allowed_types: Optional[list] = None,
    ):
        self.name = name
        self.required = required
        self.max_size = max_size
        self.allowed_types = allowed_types

    def __repr__(self):
        return f"FormFile(name={self.name}, required={self.required}, max_size={self.max_size}, allowed_types={self.allowed_types})"


class FormParam:
    """
    Marks a parameter as a form field from multipart/form-data.

    Usage:
        @PostMapping("/upload")
        async def upload(self, file: UploadFile = FormFile(), title: str = FormParam()):
            ...

        @PostMapping("/submit")
        async def submit(self, name: str = FormParam(), email: str = FormParam(default="")):
            ...
    """

    def __init__(
        self, name: Optional[str] = None, required: bool = True, default: Any = None
    ):
        self.name = name
        self.required = required
        self.default = default

    def __repr__(self):
        return f"FormParam(name={self.name}, required={self.required}, default={self.default})"


def extract_param_metadata(func) -> dict:
    """
    Extract parameter metadata from a function's type hints and defaults.
    Returns dict mapping parameter name to ParamMetadata.
    """

    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    metadata = {}

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        param_type = type_hints.get(param_name, Any)
        default = param.default

        # Check if parameter type is Request - inject it automatically
        if param_type is Request:
            metadata[param_name] = ParamMetadata(
                kind="request",
                name=param_name,
                required=True,
                param_type=Request,
            )
        # Check if default is one of our parameter markers
        elif isinstance(default, PathVariable):
            metadata[param_name] = ParamMetadata(
                kind="path",
                name=default.name or param_name,
                required=default.required,
                param_type=param_type,
            )
        elif isinstance(default, (QueryParam, RequestParam)):
            metadata[param_name] = ParamMetadata(
                kind="query",
                name=default.name or param_name,
                required=default.required,
                default=default.default,
                param_type=param_type,
            )
        elif isinstance(default, RequestBody):
            metadata[param_name] = ParamMetadata(
                kind="body",
                required=default.required,
                param_type=param_type,
            )
        elif isinstance(default, RequestHeader):
            metadata[param_name] = ParamMetadata(
                kind="header",
                name=default.name or param_name,
                required=default.required,
                default=default.default,
                param_type=param_type,
            )
        elif isinstance(default, FormFile):
            metadata[param_name] = ParamMetadata(
                kind="file",
                name=default.name or param_name,
                required=default.required,
                param_type=param_type,
                max_size=default.max_size,
                allowed_types=default.allowed_types,
            )
        elif isinstance(default, FormParam):
            metadata[param_name] = ParamMetadata(
                kind="form",
                name=default.name or param_name,
                required=default.required,
                default=default.default,
                param_type=param_type,
            )
        elif param.default == inspect.Parameter.empty:
            # No default, try to infer from context
            # If it's a complex type (not str/int/float/bool), assume it's a body
            if param_type not in (str, int, float, bool, Any) and get_origin(
                param_type
            ) not in (list, dict):
                metadata[param_name] = ParamMetadata(
                    kind="body", required=True, param_type=param_type
                )
            else:
                # Simple type with no marker - could be path or query, determined at runtime
                metadata[param_name] = ParamMetadata(
                    kind="auto", name=param_name, required=False, param_type=param_type
                )
        else:
            # Has a default value but no marker - treat as query param
            metadata[param_name] = ParamMetadata(
                kind="query",
                name=param_name,
                required=False,
                default=default,
                param_type=param_type,
            )

    return metadata
