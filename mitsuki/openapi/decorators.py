from typing import Any, Dict, List, Optional


def OpenAPIOperation(
    summary: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    responses: Optional[Dict[int, Dict[str, Any]]] = None,
    parameters: Optional[List[Dict[str, Any]]] = None,
    deprecated: bool = False,
    operation_id: Optional[str] = None,
):
    """
    Decorator to add OpenAPI operation metadata to a controller method.

    Args:
        summary: Brief summary of the operation
        description: Detailed description of the operation
        tags: List of tags for grouping operations
        responses: Custom response definitions (status_code -> response spec)
        parameters: Additional parameter documentation
        deprecated: Mark operation as deprecated
        operation_id: Custom operation ID

    Example:
        @GetMapping("/{id}")
        @OpenAPIOperation(
            summary="Get user by ID",
            description="Retrieve a single user by their unique identifier",
            tags=["Users", "Management"],
            responses={
                404: {"description": "User not found"}
            }
        )
        async def get_user(self, id: int) -> User:
            ...
    """

    def decorator(func):
        # Store metadata on function
        func.__mitsuki_openapi_operation__ = {
            "summary": summary,
            "description": description,
            "tags": tags,
            "responses": responses or {},
            "parameters": parameters or [],
            "deprecated": deprecated,
            "operation_id": operation_id,
        }
        return func

    return decorator


def OpenAPITag(
    name: str,
    description: Optional[str] = None,
    external_docs: Optional[Dict[str, str]] = None,
):
    """
    Decorator to add OpenAPI tag metadata to a controller class.

    Args:
        name: Tag name
        description: Tag description
        external_docs: External documentation (with "description" and "url")

    Example:
        @RestController("/users")
        @OpenAPITag(
            name="Users",
            description="User management and authentication",
            external_docs={
                "description": "User API Guide",
                "url": "https://docs.example.com/users"
            }
        )
        class UserController:
            ...
    """

    def decorator(cls):
        # Store metadata on class
        cls.__mitsuki_openapi_tag__ = {
            "name": name,
            "description": description,
            "externalDocs": external_docs,
        }
        return cls

    return decorator


def OpenAPISecurity(schemes: List[str]):
    """
    Decorator to specify security requirements for an operation.

    Args:
        schemes: List of security scheme names

    Example:
        @GetMapping("/protected")
        @OpenAPISecurity(["bearerAuth"])
        async def protected_endpoint(self):
            ...
    """

    def decorator(func):
        func.__mitsuki_openapi_security__ = schemes
        return func

    return decorator
