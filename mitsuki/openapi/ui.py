from typing import Dict

from starlette.responses import HTMLResponse

from mitsuki.web.controllers import RestController
from mitsuki.web.mappings import GetMapping


def create_swagger_ui_controller(docs_url: str, openapi_url: str):
    """
    Create controller that serves Swagger UI via CDN.

    Args:
        docs_url: URL path for Swagger UI (e.g., /docs)
        openapi_url: URL path for OpenAPI spec (e.g., /openapi.json)

    Returns:
        Controller class for Swagger UI
    """

    @RestController()
    class SwaggerUIController:
        """Serves Swagger UI documentation interface."""

        @GetMapping(docs_url)
        async def swagger_ui(self):
            """Serve Swagger UI HTML page."""
            html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Documentation</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = () => {{
            window.ui = SwaggerUIBundle({{
                url: '{openapi_url}',
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true,
                persistAuthorization: true,
            }});
        }};
    </script>
</body>
</html>
            """
            return HTMLResponse(html)

    return SwaggerUIController


def create_openapi_controller(spec: Dict, openapi_url: str):
    """
    Create controller that serves OpenAPI specification.

    Args:
        spec: OpenAPI specification dictionary
        openapi_url: URL path for OpenAPI spec (e.g., /openapi.json)

    Returns:
        Controller class for OpenAPI spec
    """

    @RestController()
    class OpenAPIController:
        """Serves OpenAPI specification."""

        def __init__(self):
            self.spec = spec

        @GetMapping(openapi_url)
        async def openapi_spec(self) -> Dict:
            """Serve OpenAPI 3.1 specification in JSON format."""
            return self.spec

    return OpenAPIController


def create_redoc_controller(docs_url: str, openapi_url: str):
    """
    Create controller that serves ReDoc UI via CDN.

    Args:
        docs_url: URL path for ReDoc UI (e.g., /redoc)
        openapi_url: URL path for OpenAPI spec (e.g., /openapi.json)

    Returns:
        Controller class for ReDoc UI
    """

    @RestController()
    class ReDocController:
        """Serves ReDoc documentation interface."""

        @GetMapping(docs_url)
        async def redoc_ui(self):
            """Serve ReDoc HTML page."""
            html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Documentation - ReDoc</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <redoc spec-url='{openapi_url}'></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
</body>
</html>
            """
            return HTMLResponse(html)

    return ReDocController


def create_scalar_controller(docs_url: str, openapi_url: str):
    """
    Create controller that serves Scalar UI via CDN.

    Args:
        docs_url: URL path for Scalar UI (e.g., /scalar)
        openapi_url: URL path for OpenAPI spec (e.g., /openapi.json)

    Returns:
        Controller class for Scalar UI
    """

    @RestController()
    class ScalarController:
        """Serves Scalar documentation interface."""

        @GetMapping(docs_url)
        async def scalar_ui(self):
            """Serve Scalar HTML page."""
            html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Documentation - Scalar</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <script id="api-reference" data-url="{openapi_url}"></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>
            """
            return HTMLResponse(html)

    return ScalarController
