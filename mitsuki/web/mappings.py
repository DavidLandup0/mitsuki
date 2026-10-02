import asyncio
from functools import wraps
from typing import Callable, List, Optional, Type, Union

from mitsuki.core.enums import HttpMethod, MediaType


class RouteMetadata:
    """Metadata for a route handler method."""

    def __init__(
        self,
        method: Union[HttpMethod, str],
        path: str,
        produces: Optional[str] = None,
        consumes: Optional[str] = None,
        produces_type: Optional[Type] = None,
        exclude_fields: Optional[List[str]] = None,
        consumes_type: Optional[Type] = None,
    ):
        self.method = HttpMethod.from_string(method)
        self.path = path
        self.produces = produces
        self.consumes = consumes
        self.produces_type = produces_type
        self.exclude_fields = exclude_fields or []
        self.consumes_type = consumes_type


def RequestMapping(
    path: str = "",
    method: Union[HttpMethod, str] = HttpMethod.GET,
    produces: Optional[str] = None,
    consumes: Optional[str] = None,
    return_type: Optional[Type] = None,
    produces_type: Optional[Type] = None,
    exclude_fields: Optional[List[str]] = None,
    consumes_type: Optional[Type] = None,
):
    """
    Generic request mapping decorator.

    Args:
        path: URL path for this route (relative to controller base path)
        method: HTTP method as HttpMethod (or its string name, case-insensitive)
        produces: Media type this endpoint produces (e.g., "application/json")
        consumes: Media type this endpoint consumes (e.g., "application/json")
        return_type: Expected return type for validation/conversion (alias for produces_type)
        produces_type: Expected output type for validation/conversion
        exclude_fields: Fields to exclude from JSON output
        consumes_type: Expected input type for validation/conversion
    """

    def decorator(func: Callable) -> Callable:
        # Check if @Produces or @Consumes were applied before this decorator
        decorator_produces_type = getattr(func, "__mitsuki_produces_type__", None)
        decorator_consumes_type = getattr(func, "__mitsuki_consumes_type__", None)

        # Merge all sources: return_type is alias for produces_type
        final_produces_type = produces_type or return_type or decorator_produces_type
        final_consumes_type = consumes_type or decorator_consumes_type

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # If the original function is async, await it
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                # Run sync function in executor to avoid blocking
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

        # Store route metadata
        wrapper.__mitsuki_route__ = RouteMetadata(
            method=resolved_method,
            path=path,
            produces=produces,
            consumes=consumes,
            produces_type=final_produces_type,
            exclude_fields=exclude_fields,
            consumes_type=final_consumes_type,
        )

        return wrapper

    resolved_method = HttpMethod.from_string(method)

    return decorator


def GetMapping(
    path: str = "",
    produces: Optional[str] = MediaType.APPLICATION_JSON,
    return_type: Optional[Type] = None,
    produces_type: Optional[Type] = None,
    exclude_fields: Optional[List[str]] = None,
):
    """
    GET request mapping decorator.

    Args:
        path: URL path for this route
        produces: Media type this endpoint produces
        return_type: Expected return type for validation/conversion (alias for produces_type)
        produces_type: Expected output type for validation/conversion
        exclude_fields: Fields to exclude from JSON output
    """
    return RequestMapping(
        path=path,
        method=HttpMethod.GET,
        produces=produces,
        return_type=return_type,
        produces_type=produces_type,
        exclude_fields=exclude_fields,
    )


def PostMapping(
    path: str = "",
    produces: Optional[str] = MediaType.APPLICATION_JSON,
    consumes: Optional[str] = MediaType.APPLICATION_JSON,
    return_type: Optional[Type] = None,
    produces_type: Optional[Type] = None,
    consumes_type: Optional[Type] = None,
    exclude_fields: Optional[List[str]] = None,
):
    """
    POST request mapping decorator.

    Args:
        path: URL path for this route
        produces: Media type this endpoint produces
        consumes: Media type this endpoint consumes
        return_type: Expected return type for validation/conversion (alias for produces_type)
        produces_type: Expected output type for validation/conversion
        consumes_type: Expected input type for validation/conversion
        exclude_fields: Fields to exclude from JSON output
    """
    return RequestMapping(
        path=path,
        method=HttpMethod.POST,
        produces=produces,
        consumes=consumes,
        return_type=return_type,
        produces_type=produces_type,
        consumes_type=consumes_type,
        exclude_fields=exclude_fields,
    )


def PutMapping(
    path: str = "",
    produces: Optional[str] = MediaType.APPLICATION_JSON,
    consumes: Optional[str] = MediaType.APPLICATION_JSON,
    return_type: Optional[Type] = None,
    produces_type: Optional[Type] = None,
    consumes_type: Optional[Type] = None,
    exclude_fields: Optional[List[str]] = None,
):
    """
    PUT request mapping decorator.

    Args:
        path: URL path for this route
        produces: Media type this endpoint produces
        consumes: Media type this endpoint consumes
        return_type: Expected return type for validation/conversion (alias for produces_type)
        produces_type: Expected output type for validation/conversion
        consumes_type: Expected input type for validation/conversion
        exclude_fields: Fields to exclude from JSON output
    """
    return RequestMapping(
        path=path,
        method=HttpMethod.PUT,
        produces=produces,
        consumes=consumes,
        return_type=return_type,
        produces_type=produces_type,
        consumes_type=consumes_type,
        exclude_fields=exclude_fields,
    )


def DeleteMapping(
    path: str = "",
    produces: Optional[str] = MediaType.APPLICATION_JSON,
    return_type: Optional[Type] = None,
    produces_type: Optional[Type] = None,
    exclude_fields: Optional[List[str]] = None,
):
    """
    DELETE request mapping decorator.

    Args:
        path: URL path for this route
        produces: Media type this endpoint produces
        return_type: Expected return type for validation/conversion (alias for produces_type)
        produces_type: Expected output type for validation/conversion
        exclude_fields: Fields to exclude from JSON output
    """
    return RequestMapping(
        path=path,
        method=HttpMethod.DELETE,
        produces=produces,
        return_type=return_type,
        produces_type=produces_type,
        exclude_fields=exclude_fields,
    )


def PatchMapping(
    path: str = "",
    produces: Optional[str] = MediaType.APPLICATION_JSON,
    consumes: Optional[str] = MediaType.APPLICATION_JSON,
    return_type: Optional[Type] = None,
    produces_type: Optional[Type] = None,
    consumes_type: Optional[Type] = None,
    exclude_fields: Optional[List[str]] = None,
):
    """
    PATCH request mapping decorator.

    Args:
        path: URL path for this route
        produces: Media type this endpoint produces
        consumes: Media type this endpoint consumes
        return_type: Expected return type for validation/conversion (alias for produces_type)
        produces_type: Expected output type for validation/conversion
        consumes_type: Expected input type for validation/conversion
        exclude_fields: Fields to exclude from JSON output
    """
    return RequestMapping(
        path=path,
        method=HttpMethod.PATCH,
        produces=produces,
        consumes=consumes,
        return_type=return_type,
        produces_type=produces_type,
        consumes_type=consumes_type,
        exclude_fields=exclude_fields,
    )


def Produces(type_or_dto: Optional[Type] = None):
    """
    Decorator to specify the output type for validation/conversion.
    Can be used with or without type parameter.

    Usage:
        @Produces(UserDTO)
        @Produces(type=UserDTO)

    This is equivalent to setting return_type on mapping decorators.
    """

    def decorator(func: Callable) -> Callable:
        # Get existing route metadata or create empty dict
        if hasattr(func, "__mitsuki_route__"):
            func.__mitsuki_route__.produces_type = type_or_dto
        else:
            # Store as temporary attribute to be picked up by mapping decorator
            func.__mitsuki_produces_type__ = type_or_dto
        return func

    # Support both @Produces(UserDTO) and @Produces(type=UserDTO)
    if (
        type_or_dto is not None
        and callable(type_or_dto)
        and not isinstance(type_or_dto, type)
    ):
        # Called as @Produces without parens - type_or_dto is the function
        func = type_or_dto
        func.__mitsuki_produces_type__ = None
        return func

    return decorator


def Consumes(type_or_dto: Optional[Type] = None):
    """
    Decorator to specify the input type for validation.
    Can be used with or without type parameter.

    Usage:
        @Consumes(CreateUserRequest)
        @Consumes(type=CreateUserRequest)

    This validates and converts request body to the specified type.
    """

    def decorator(func: Callable) -> Callable:
        # Get existing route metadata or create empty dict
        if hasattr(func, "__mitsuki_route__"):
            func.__mitsuki_route__.consumes_type = type_or_dto
        else:
            # Store as temporary attribute to be picked up by mapping decorator
            func.__mitsuki_consumes_type__ = type_or_dto
        return func

    # Support both @Consumes(UserDTO) and @Consumes(type=UserDTO)
    if (
        type_or_dto is not None
        and callable(type_or_dto)
        and not isinstance(type_or_dto, type)
    ):
        # Called as @Consumes without parens - type_or_dto is the function
        func = type_or_dto
        func.__mitsuki_consumes_type__ = None
        return func

    return decorator


# Shorter aliases for mapping decorators
Get = GetMapping
Post = PostMapping
Put = PutMapping
Delete = DeleteMapping
Patch = PatchMapping
