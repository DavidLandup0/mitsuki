from typing import Any, Callable, List, Optional, Union

import msgspec
from starlette.requests import Request

from mitsuki.core.enums import ParameterKind
from mitsuki.exceptions import (
    FileTooLargeException,
    InvalidFileTypeException,
    RequestValidationException,
)
from mitsuki.web.converters import build_converter, decode_json, is_sequence_hint
from mitsuki.web.multipart import parse_multipart

_MISSING = object()

Converter = Optional[Callable[[Any], Any]]
Extractor = Callable[[Request, Any], Any]


class ValueBinder(msgspec.Struct):
    """
    Reads one value from a single request source.

    Path, query, header, form and unmarked parameters differ only in where the
    raw value comes from, so they share this binder and supply an extractor.
    """

    param: str
    source: str
    extract: Extractor
    required: bool
    default: Any
    converter: Converter
    needs_form: bool = False
    needs_body: bool = False

    def bind(self, request: Request, form: Any, body: Any) -> Any:
        value = self.extract(request, form)
        if value is _MISSING:
            if self.default is not None:
                return self.default
            if self.required:
                raise RequestValidationException(
                    f"Required {self.source} '{self.param}' not found"
                )
            return None
        return self.converter(value) if self.converter else value


class BodyBinder(msgspec.Struct):
    """Decodes and validates the JSON request body."""

    needs_form = False
    needs_body = True

    param: str
    required: bool
    hint: Any

    def bind(self, request: Request, form: Any, body: Any) -> Any:
        if not body:
            if self.required:
                raise RequestValidationException("Required request body not provided")
            return None
        return decode_json(body, self.hint)


class FileBinder(msgspec.Struct):
    """Reads one or more uploaded files from a multipart form."""

    needs_form = True
    needs_body = False

    param: str
    field: str
    required: bool
    multi: bool
    allowed_types: Optional[list]
    max_size: Optional[int]

    def bind(self, request: Request, form: Any, body: Any) -> Any:
        if self.multi:
            files = form.get_files(self.field)
        else:
            single = form.get_file(self.field)
            files = [single] if single else []

        if not files:
            if self.required:
                raise RequestValidationException(
                    f"Required file parameter '{self.param}' not found"
                )
            return [] if self.multi else None

        for file in files:
            if self.allowed_types and file.content_type not in self.allowed_types:
                raise InvalidFileTypeException(
                    f"File type {file.content_type} not allowed for '{self.param}'. "
                    f"Allowed types: {self.allowed_types}"
                )
            if self.max_size and file.size > self.max_size:
                raise FileTooLargeException(
                    f"File {file.filename} exceeds maximum size {self.max_size} bytes"
                )

        return files if self.multi else files[0]


def _from_path(field: str) -> Extractor:
    return lambda request, form: request.path_params.get(field, _MISSING)


def _from_query(field: str, multi: bool) -> Extractor:
    if multi:
        return lambda request, form: request.query_params.getlist(field) or _MISSING
    return lambda request, form: request.query_params.get(field, _MISSING)


def _from_header(field: str) -> Extractor:
    return lambda request, form: request.headers.get(field, _MISSING)


def _from_form(field: str, multi: bool) -> Extractor:
    if multi:
        return lambda request, form: form.get_fields(field) or _MISSING
    return lambda request, form: (
        value if (value := form.get_field(field)) is not None else _MISSING
    )


def _from_path_or_query(field: str) -> Extractor:
    """Unmarked parameters prefer the path, then fall back to the query string."""

    def extract(request: Request, form: Any) -> Any:
        value = request.path_params.get(field, _MISSING)
        if value is _MISSING:
            return request.query_params.get(field, _MISSING)
        return value

    return extract


class RequestLimits(msgspec.Struct):
    """Size limits applied while reading a request."""

    max_body_size: int
    max_file_size: int
    max_request_size: int


def _is_json_content_type(content_type: str) -> bool:
    """Accept application/json and its structured suffixes (e.g. +json)."""
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.startswith("application/json") or media_type.endswith("+json")


class BindingPlan:
    """A prebuilt set of binders for one route."""

    __slots__ = ("binders", "needs_form", "needs_body", "limits")

    def __init__(self, binders: list, limits: RequestLimits):
        self.binders = tuple(binders)
        self.needs_form = any(binder.needs_form for binder in binders)
        self.needs_body = any(binder.needs_body for binder in binders)
        self.limits = limits

    async def bind(self, request: Request) -> dict:
        """Build handler arguments from an HTTP request."""
        body = await self._read_body(request) if self.needs_body else None
        form = await self._read_form(request) if self.needs_form else None

        return {b.param: b.bind(request, form, body) for b in self.binders}

    async def _read_body(self, request: Request) -> bytes:
        """Read the JSON body, enforcing max_body_size."""
        body = await self._read_capped(request, self.limits.max_body_size)

        content_type = request.headers.get("content-type", "")
        if body and content_type and not _is_json_content_type(content_type):
            raise RequestValidationException(
                f"Unsupported Content-Type: {content_type}. Expected application/json"
            )

        return body

    async def _read_form(self, request: Request):
        """Parse the multipart body, enforcing max_request_size."""
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            raise RequestValidationException("Expected multipart/form-data")

        body = await self._read_capped(request, self.limits.max_request_size)
        return await parse_multipart(
            content_type,
            body,
            max_file_size=self.limits.max_file_size,
            max_request_size=self.limits.max_request_size,
        )

    async def _read_capped(self, request: Request, max_size: int) -> bytes:
        """Read the body, stopping once it exceeds max_size, even without Content-Length."""
        too_large = f"Request body too large (max {max_size} bytes)"

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_size:
            raise RequestValidationException(too_large)

        chunks = bytearray()
        async for chunk in request.stream():
            chunks += chunk
            if len(chunks) > max_size:
                raise RequestValidationException(too_large)

        body = bytes(chunks)
        # Populate Starlette's body cache so handlers and middleware that call
        # request.body() later do not hit an already-consumed stream.
        request._body = body
        return body


class ParameterBinder:
    """Builds binding plans for routes."""

    def __init__(self, max_body_size: int, max_file_size: int, max_request_size: int):
        self.limits = RequestLimits(max_body_size, max_file_size, max_request_size)

    def build_plan(self, param_metadata: dict, route_meta: Any) -> BindingPlan:
        """Build the binding plan for a handler. Called once, at registration."""
        consumes_type = route_meta.consumes_type if route_meta else None
        binders = [
            self._build_binder(param, metadata, consumes_type)
            for param, metadata in param_metadata.items()
        ]
        return BindingPlan(binders, self.limits)

    def _build_binder(self, param: str, metadata: Any, consumes_type: Optional[type]):
        kind = metadata.kind
        field = metadata.name or param
        hint = metadata.param_type
        converter = build_converter(hint)
        multi = is_sequence_hint(hint)

        if kind == ParameterKind.BODY:
            if consumes_type:
                # @Consumes wins over the annotation, and accepts either a single
                # object or an array of them.
                hint = Union[consumes_type, List[consumes_type]]
            return BodyBinder(param, metadata.required, hint)

        if kind == ParameterKind.FILE:
            return FileBinder(
                param,
                field,
                metadata.required,
                multi,
                metadata.allowed_types,
                metadata.max_size,
            )

        if kind == ParameterKind.REQUEST:
            return ValueBinder(
                param, "request", lambda request, form: request, False, None, None
            )

        if kind == ParameterKind.PATH:
            return ValueBinder(
                param,
                "path parameter",
                _from_path(field),
                metadata.required,
                None,
                converter,
            )

        if kind == ParameterKind.QUERY:
            return ValueBinder(
                param,
                "query parameter",
                _from_query(field, multi),
                metadata.required,
                metadata.default,
                converter,
            )

        if kind == ParameterKind.HEADER:
            return ValueBinder(
                param,
                "header",
                _from_header(field.lower()),
                metadata.required,
                metadata.default,
                converter,
            )

        if kind == ParameterKind.FORM:
            return ValueBinder(
                param,
                "form parameter",
                _from_form(field, multi),
                metadata.required,
                metadata.default,
                converter,
                needs_form=True,
            )

        if kind == ParameterKind.AUTO:
            return ValueBinder(
                param, "parameter", _from_path_or_query(field), False, None, converter
            )

        raise ValueError(f"Unknown parameter kind '{kind}' for parameter '{param}'")
