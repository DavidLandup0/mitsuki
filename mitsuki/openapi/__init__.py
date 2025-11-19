from enum import Enum
from typing import TYPE_CHECKING

from mitsuki.openapi.decorators import OpenAPIOperation, OpenAPISecurity, OpenAPITag
from mitsuki.openapi.generator import generate_openapi_spec
from mitsuki.openapi.ui import (
    create_openapi_controller,
    create_redoc_controller,
    create_scalar_controller,
    create_swagger_ui_controller,
)

if TYPE_CHECKING:
    from mitsuki.core.application import ApplicationContext


class UIType(str, Enum):
    """OpenAPI documentation UI types."""

    SWAGGER = "swagger"
    REDOC = "redoc"
    SCALAR = "scalar"


__all__ = [
    "register_openapi_endpoints",
    "generate_openapi_spec",
    "OpenAPIOperation",
    "OpenAPITag",
    "OpenAPISecurity",
]


def register_openapi_endpoints(context: "ApplicationContext", config):
    """
    Register OpenAPI documentation endpoints if enabled.

    Creates and registers:
    - Configured docs_ui at /docs
    - All enabled UIs at their respective paths (/swagger, /redoc, /scalar)
    - OpenAPI spec at configured openapi_url

    Args:
        context: Application context
        config: Configuration object

    Returns:
        None
    """
    # Check if OpenAPI is enabled
    if not config.get_bool("openapi.enabled"):
        return

    docs_url = config.get("openapi.docs_url")
    openapi_url = config.get("openapi.openapi_url")
    docs_ui = config.get("openapi.docs_ui")

    # Get UI list from config
    ui_config = config.get("openapi.ui")
    if isinstance(ui_config, str):
        ui_list = [ui_config]
    else:
        ui_list = ui_config

    # Generate OpenAPI specification
    spec = generate_openapi_spec(context, config)

    # Create OpenAPI spec controller
    openapi_controller = create_openapi_controller(spec, openapi_url)
    context.controllers.append((openapi_controller, ""))

    # Create controller for docs_ui at /docs
    try:
        docs_ui_type = UIType(docs_ui.lower())
        if docs_ui_type == UIType.SWAGGER:
            docs_controller = create_swagger_ui_controller(docs_url, openapi_url)
        elif docs_ui_type == UIType.REDOC:
            docs_controller = create_redoc_controller(docs_url, openapi_url)
        elif docs_ui_type == UIType.SCALAR:
            docs_controller = create_scalar_controller(docs_url, openapi_url)
        else:
            docs_controller = None

        if docs_controller:
            context.controllers.append((docs_controller, ""))
    except (ValueError, AttributeError):
        pass

    # Create UI controllers for each enabled UI at their named paths
    for ui_str in ui_list:
        try:
            ui_type = UIType(ui_str.lower())
        except ValueError:
            continue

        # Each UI gets its own named path
        url = f"/{ui_type.value}"

        # Create controller based on UI type
        if ui_type == UIType.SWAGGER:
            ui_controller = create_swagger_ui_controller(url, openapi_url)
        elif ui_type == UIType.REDOC:
            ui_controller = create_redoc_controller(url, openapi_url)
        elif ui_type == UIType.SCALAR:
            ui_controller = create_scalar_controller(url, openapi_url)
        else:
            continue

        context.controllers.append((ui_controller, ""))
