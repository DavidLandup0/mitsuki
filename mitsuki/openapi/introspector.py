import inspect
from typing import Any, Dict, get_type_hints

from mitsuki.core.enums import ParameterKind
from mitsuki.openapi.schemas import type_to_schema
from mitsuki.web.params import extract_param_metadata


def extract_operation(method, route_meta, controller_name: str) -> Dict[str, Any]:
    """
    Extract OpenAPI operation from a controller method.

    Uses existing Mitsuki metadata:
    - route_meta.method → HTTP method
    - route_meta.path → URL path
    - route_meta.consumes_type → request body schema
    - route_meta.produces_type → response schema
    - Docstring → operation description
    - ParamMetadata → parameters

    Args:
        method: Controller method
        route_meta: RouteMetadata from @GetMapping, @PostMapping, etc.
        controller_name: Name of controller class for tagging

    Returns:
        OpenAPI operation dictionary
    """
    # Check for optional @OpenAPIOperation decorator metadata
    openapi_meta = getattr(method, "__mitsuki_openapi_operation__", {})

    # Extract summary from decorator (if provided) or auto-generate from method name
    summary = (
        openapi_meta.get("summary")
        if openapi_meta.get("summary")
        else method.__name__.replace("_", " ").title()
    )

    # Extract description from decorator (if provided) or from docstring
    description = (
        openapi_meta.get("description")
        if openapi_meta.get("description")
        else (inspect.getdoc(method) or "")
    )

    # Use custom tags from decorator (if provided) or default to controller name
    tags = openapi_meta.get("tags") if openapi_meta.get("tags") else [controller_name]

    # Use custom operation_id from decorator (if provided) or auto-generate
    operation_id = (
        openapi_meta.get("operation_id")
        if openapi_meta.get("operation_id")
        else f"{controller_name}_{method.__name__}"
    )

    operation = {
        "tags": tags,
        "summary": summary,
        "operationId": operation_id,
        "parameters": [],
        "responses": {},
    }

    if description:
        operation["description"] = description

    # Mark as deprecated if specified in decorator
    if openapi_meta.get("deprecated"):
        operation["deprecated"] = True

    # Extract parameters from existing ParamMetadata
    param_metadata = extract_param_metadata(method)

    for param_name, metadata in param_metadata.items():
        # Skip body parameters (handled separately)
        if metadata.kind == ParameterKind.BODY:
            continue

        # Skip file/form parameters for now (handled in requestBody)
        if metadata.kind in (ParameterKind.FILE, ParameterKind.FORM):
            continue

        param_schema = _param_to_openapi(param_name, metadata)
        if param_schema:
            operation["parameters"].append(param_schema)

    # Merge in additional parameter documentation from decorator
    decorator_params = openapi_meta.get("parameters") or []
    for decorator_param in decorator_params:
        # Find matching parameter by name and merge
        param_name = decorator_param.get("name")
        existing_param = next(
            (p for p in operation["parameters"] if p.get("name") == param_name), None
        )
        if existing_param:
            # Merge decorator metadata into existing parameter
            existing_param.update(
                {k: v for k, v in decorator_param.items() if v is not None}
            )
        else:
            # Add new parameter from decorator
            operation["parameters"].append(decorator_param)

    # Auto-detect request body type from method signature if not explicitly set
    consumes_type = route_meta.consumes_type
    if not consumes_type:
        consumes_type = _infer_request_body_type(method, param_metadata)

    # Request body from consumes_type or inferred type
    if consumes_type:
        operation["requestBody"] = {
            "required": True,
            "content": {
                route_meta.consumes or "application/json": {
                    "schema": type_to_schema(consumes_type)
                }
            },
        }

    # Auto-detect response type from return annotation if not explicitly set
    produces_type = route_meta.produces_type
    if not produces_type:
        produces_type = _infer_response_type(method)

    # Response from produces_type, inferred type, or default
    response_schema = (
        type_to_schema(produces_type) if produces_type else {"type": "object"}
    )

    operation["responses"]["200"] = {
        "description": "Successful response",
        "content": {
            route_meta.produces or "application/json": {"schema": response_schema}
        },
    }

    # Add common error responses
    operation["responses"]["400"] = {
        "description": "Bad request",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"error": {"type": "string"}},
                }
            }
        },
    }

    operation["responses"]["500"] = {
        "description": "Internal server error",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"error": {"type": "string"}},
                }
            }
        },
    }

    # Merge in custom responses from decorator
    decorator_responses = openapi_meta.get("responses") or {}
    for status_code, response_spec in decorator_responses.items():
        # Convert status code to string for OpenAPI
        status_str = str(status_code)
        # Decorator responses override auto-generated ones
        operation["responses"][status_str] = response_spec

    return operation


def _infer_request_body_type(method, param_metadata: Dict):
    """
    Infer request body type from method parameters.

    Looks for a parameter with ParameterKind.BODY and extracts its type.

    Args:
        method: Controller method
        param_metadata: Extracted parameter metadata

    Returns:
        Type annotation for request body or None
    """
    # Look for BODY parameter
    for param_name, metadata in param_metadata.items():
        if metadata.kind == ParameterKind.BODY:
            return metadata.param_type
    return None


def _infer_response_type(method):
    """
    Infer response type from method return annotation.

    Args:
        method: Controller method

    Returns:
        Type annotation for response or None
    """
    try:
        type_hints = get_type_hints(method)
        return_type = type_hints.get("return")
        # Skip None, NoneType, and inspect._empty
        if return_type and return_type is not type(None):
            return return_type
    except Exception:
        pass
    return None


def _param_to_openapi(param_name: str, metadata) -> Dict[str, Any]:
    """
    Convert ParamMetadata to OpenAPI parameter.

    Args:
        param_name: Parameter name
        metadata: ParamMetadata instance

    Returns:
        OpenAPI parameter dictionary or None if not applicable
    """
    # Map ParameterKind to OpenAPI 'in' location
    kind_to_location = {
        ParameterKind.PATH: "path",
        ParameterKind.QUERY: "query",
        ParameterKind.HEADER: "header",
    }

    location = kind_to_location.get(metadata.kind)
    if not location:
        return None

    param = {
        "name": metadata.name or param_name,
        "in": location,
        "required": metadata.required,
    }

    # Add schema
    if metadata.param_type:
        param["schema"] = type_to_schema(metadata.param_type)
    else:
        param["schema"] = {"type": "string"}

    # Add default value if present
    if metadata.default is not None:
        param["schema"]["default"] = metadata.default

    return param


def extract_paths(controller_cls, base_path: str) -> Dict[str, Dict]:
    """
    Extract all paths from a controller.

    Args:
        controller_cls: Controller class
        base_path: Base path from @RestController

    Returns:
        Dictionary of paths with operations
    """
    paths = {}
    controller_name = controller_cls.__name__

    # Scan all methods (use isfunction since controller is not instantiated)
    for name, method in inspect.getmembers(
        controller_cls, predicate=inspect.isfunction
    ):
        # Skip private methods
        if name.startswith("_"):
            continue

        # Check if method has route metadata
        if not hasattr(method, "__mitsuki_route__"):
            continue

        route_meta = method.__mitsuki_route__

        # Combine base path and route path
        full_path = _combine_paths(base_path, route_meta.path)

        # Initialize path if not exists
        if full_path not in paths:
            paths[full_path] = {}

        # Extract operation
        http_method = route_meta.method.lower()
        operation = extract_operation(method, route_meta, controller_name)

        paths[full_path][http_method] = operation

    return paths


def _combine_paths(base: str, route: str) -> str:
    """Combine base path and route path."""
    base = base.rstrip("/")
    route = route.rstrip("/")

    if not route:
        return base or "/"

    if not base:
        return route or "/"

    return f"{base}{route}"
