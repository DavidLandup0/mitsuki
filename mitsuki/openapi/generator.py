from typing import TYPE_CHECKING, Any, Dict

from mitsuki.openapi.introspector import extract_paths
from mitsuki.openapi.schemas import clear_schema_registry, get_schema_registry

if TYPE_CHECKING:
    from mitsuki.core.application import ApplicationContext


def generate_openapi_spec(context: "ApplicationContext", config) -> Dict[str, Any]:
    """
    Generate OpenAPI 3.1 specification from application context.

    Leverages existing Mitsuki metadata:
    - Controllers → paths and tags
    - RouteMetadata → operations
    - ParamMetadata → parameters
    - Type hints → schemas

    Args:
        context: Application context with controllers
        config: Configuration object

    Returns:
        OpenAPI 3.1 specification dictionary
    """
    # Clear schema registry before generating new spec
    clear_schema_registry()

    spec = {
        "openapi": "3.1.0",
        "info": _build_info(config),
        "paths": {},
        "components": {"schemas": {}},
    }

    # Add servers if configured
    servers = _build_servers(config)
    if servers:
        spec["servers"] = servers

    # Build paths from all controllers
    for controller_cls, base_path in context.controllers:
        paths = extract_paths(controller_cls, base_path)
        # Merge paths into spec
        for path, operations in paths.items():
            if path not in spec["paths"]:
                spec["paths"][path] = {}
            spec["paths"][path].update(operations)

    # Add collected schemas from registry
    schemas = get_schema_registry()
    if schemas:
        spec["components"]["schemas"] = schemas

    return spec


def _build_info(config) -> Dict[str, Any]:
    """
    Build OpenAPI info object from configuration.

    Args:
        config: Configuration object

    Returns:
        Info dictionary
    """
    info = {
        "title": config.get("openapi.title"),
        "version": config.get("openapi.version"),
    }

    # Optional description
    description = config.get("openapi.description")
    if description:
        info["description"] = description

    # Optional contact
    contact_name = config.get("openapi.contact.name")
    if contact_name:
        contact = {"name": contact_name}

        contact_email = config.get("openapi.contact.email")
        if contact_email:
            contact["email"] = contact_email

        contact_url = config.get("openapi.contact.url")
        if contact_url:
            contact["url"] = contact_url

        info["contact"] = contact

    # Optional license
    license_name = config.get("openapi.license.name")
    if license_name:
        license_info = {"name": license_name}

        license_url = config.get("openapi.license.url")
        if license_url:
            license_info["url"] = license_url

        info["license"] = license_info

    return info


def _build_servers(config) -> list:
    """
    Build OpenAPI servers array from configuration.

    Args:
        config: Configuration object

    Returns:
        List of server objects
    """
    servers = []

    # Optional server URL
    server_url = config.get("openapi.server.url")
    if server_url:
        server = {"url": server_url}

        server_description = config.get("openapi.server.description")
        if server_description:
            server["description"] = server_description

        servers.append(server)

    return servers
