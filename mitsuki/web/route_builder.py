import inspect
import logging
from typing import Any, Callable, List

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from mitsuki.core.container import get_container
from mitsuki.exceptions import (
    FileTooLargeException,
    InvalidContentTypeException,
    InvalidFileTypeException,
    RequestValidationException,
)
from mitsuki.web.parameter_binder import ParameterBinder
from mitsuki.web.params import extract_param_metadata
from mitsuki.web.response import ResponseEntity
from mitsuki.web.response_processor import ResponseProcessor
from mitsuki.web.serialization import serialize_json


class RouteBuilder:
    """Handles building routes from Mitsuki controllers."""

    def __init__(
        self,
        context,
        parameter_binder: ParameterBinder,
        response_processor: ResponseProcessor,
        ignore_trailing_slash: bool,
        debug_mode: bool,
    ):
        self.context = context
        self.parameter_binder = parameter_binder
        self.response_processor = response_processor
        self.ignore_trailing_slash = ignore_trailing_slash
        self.debug_mode = debug_mode

    def build_routes(self) -> List[Route]:
        """Build routes from Mitsuki controllers."""
        routes = []
        container = get_container()

        for controller_cls, base_path in self.context.controllers:
            controller_instance = container.get(controller_cls)

            # Find all route handlers
            for name, method in inspect.getmembers(
                controller_instance, predicate=inspect.ismethod
            ):
                if hasattr(method, "__mitsuki_route__"):
                    route_meta = method.__mitsuki_route__
                    full_path = self._combine_paths(base_path, route_meta.path)
                    param_metadata = extract_param_metadata(method)
                    endpoint = self._create_endpoint(method, param_metadata, route_meta)

                    # Register route
                    route = Route(
                        path=full_path,
                        endpoint=endpoint,
                        methods=[route_meta.method],
                    )
                    routes.append(route)

                    # If trailing slash handling is enabled, register both /path and /path/
                    if (
                        self.ignore_trailing_slash
                        and len(full_path) > 1
                        and not full_path.endswith("/")
                    ):
                        route_with_slash = Route(
                            path=full_path + "/",
                            endpoint=endpoint,
                            methods=[route_meta.method],
                        )
                        routes.append(route_with_slash)

        # Sort routes: specific paths before parameterized paths
        routes.sort(key=self._route_priority)

        return routes

    def _create_endpoint(
        self, handler: Callable, param_metadata: dict, route_meta: Any
    ):
        """
        Create an endpoint wrapper for a Mitsuki handler.
        Handles parameter extraction, validation, and response processing.
        """
        has_params = bool(param_metadata)
        produces_type = route_meta.produces_type if route_meta else None
        exclude_fields = route_meta.exclude_fields if route_meta else []
        needs_processing = produces_type is not None or exclude_fields

        async def endpoint(request: Request):
            try:
                # Build handler arguments and call handler
                if has_params:
                    handler_args = await self.parameter_binder.bind_parameters(
                        request, param_metadata, route_meta
                    )
                    result = await handler(**handler_args)
                else:
                    result = await handler()

                # If handler returns a Starlette Response, return it directly
                if isinstance(result, Response):
                    return result

                # Handle ResponseEntity
                if isinstance(result, ResponseEntity):
                    body = result.body
                    if needs_processing:
                        body = self.response_processor.process_response_data(
                            body, produces_type, exclude_fields
                        )

                    headers = dict(result.headers) if result.headers else {}

                    # Auto-detect content type if not explicitly set
                    if "content-type" not in headers and "Content-Type" not in headers:
                        if body is None:
                            content = b""
                            headers["content-type"] = "application/json"
                        elif isinstance(body, bytes):
                            content = body
                            headers["content-type"] = "application/octet-stream"
                        elif isinstance(body, str):
                            content = body.encode("utf-8")
                            headers["content-type"] = "text/plain; charset=utf-8"
                        else:
                            # dict, list, or other JSON-serializable types
                            content = serialize_json(body)
                            headers["content-type"] = "application/json"
                    else:
                        # User set custom Content-Type, respect it and serialize accordingly
                        if isinstance(body, bytes):
                            content = body
                        elif isinstance(body, str):
                            content = body.encode("utf-8")
                        else:
                            content = serialize_json(body)

                    return Response(
                        content=content,
                        status_code=result.status,
                        headers=headers,
                    )
                else:
                    # Simple response
                    if needs_processing:
                        result = self.response_processor.process_response_data(
                            result, produces_type, exclude_fields
                        )
                    content = serialize_json(result)
                    return Response(
                        content=content,
                        status_code=200,
                        headers={"content-type": "application/json"},
                    )

            except (
                ValueError,
                RequestValidationException,
                InvalidContentTypeException,
                FileTooLargeException,
                InvalidFileTypeException,
            ) as e:
                content = serialize_json({"error": str(e)})
                return Response(
                    content=content,
                    status_code=400,
                    headers={"content-type": "application/json"},
                )
            except Exception as e:
                if self.debug_mode:
                    logging.exception("Error handling request")
                    content = serialize_json(
                        {"error": str(e), "type": type(e).__name__}
                    )
                    return Response(
                        content=content,
                        status_code=500,
                        headers={"content-type": "application/json"},
                    )
                else:
                    logging.error(f"Internal server error: {e}")
                    content = serialize_json({"error": "Internal server error"})
                    return Response(
                        content=content,
                        status_code=500,
                        headers={"content-type": "application/json"},
                    )

        return endpoint

    def _combine_paths(self, base: str, route: str) -> str:
        """Combine base path and route path."""
        base = base.rstrip("/")
        route = route.rstrip("/")

        if not route:
            return base or "/"

        if not base:
            return route or "/"

        return f"{base}{route}"

    def _route_priority(self, route: Route):
        """Calculate route priority for sorting. Specific paths before parameterized paths."""
        path = route.path
        segments = [s for s in path.split("/") if s]
        param_count = sum(1 for s in segments if s.startswith("{"))
        return (param_count, -len(segments), path)
