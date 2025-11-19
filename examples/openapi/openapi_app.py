from mitsuki import Application, GetMapping, RestController
from mitsuki.openapi import OpenAPIOperation, OpenAPITag


@RestController()
@OpenAPITag(
    name="Greetings", description="Greeting endpoints with custom OpenAPI metadata"
)
class HelloController:
    @GetMapping("/")
    async def hello(self):
        """Default hello endpoint."""
        return {"message": "Hello, World!"}

    @GetMapping("/custom")
    @OpenAPIOperation(
        summary="Custom greeting with metadata",
        description="Demonstrates custom OpenAPI metadata with decorators",
        tags=["Greetings", "Examples"],
        responses={
            200: {
                "description": "Success with custom response",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "greeting": {"type": "string"},
                                "timestamp": {"type": "string"},
                            },
                        }
                    }
                },
            }
        },
        deprecated=False,
    )
    async def custom_greeting(self):
        """Endpoint with custom OpenAPI metadata."""
        from datetime import datetime

        return {"greeting": "Custom Hello!", "timestamp": datetime.now().isoformat()}

    @GetMapping("/search")
    @OpenAPIOperation(
        summary="Search with parameters",
        description="Example of parameter documentation",
        parameters=[
            {
                "name": "q",
                "description": "Search query string",
                "example": "hello world",
            },
            {
                "name": "limit",
                "description": "Maximum number of results",
                "example": 10,
            },
        ],
    )
    async def search(self, q: str, limit: int = 10):
        """Search endpoint with documented parameters."""
        return {"query": q, "limit": limit, "results": []}


@Application
class OpenAPIExampleApp:
    pass


if __name__ == "__main__":
    OpenAPIExampleApp.run()
