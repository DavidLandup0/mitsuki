# OpenAPI Documentation

Automatic OpenAPI 3.0 specification generation with multiple UI options.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Multiple UIs](#multiple-uis)
- [Customizing Documentation](#customizing-documentation)
- [Decorators](#decorators)
- [Schema Generation](#schema-generation)
- [Security Schemes](#security-schemes)
- [Best Practices](#best-practices)


## Overview

Mitsuki automatically generates OpenAPI 3.0 specifications from your controllers, including:
- **Automatic endpoint discovery** - All `@RestController` routes
- **Type inference** - Request/response schemas from type hints
- **Multiple UIs** - Swagger UI, ReDoc, and Scalar
- **Zero configuration** - Works out of the box
- **Customizable** - Add descriptions, tags, examples via decorators

**Available by default:**
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`
- **Documentation UI:** `http://localhost:8000/docs` (Scalar by default)


## Quick Start

### Default Setup (Zero Configuration)

```python
from mitsuki import Application, RestController, GetMapping

@RestController("/api/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: int) -> dict:
        """Get user by ID."""
        return {"id": id, "name": "John Doe"}

@Application
class MyApp:
    pass

if __name__ == "__main__":
    MyApp.run()
```

Visit:
- `http://localhost:8000/docs` - Interactive documentation
- `http://localhost:8000/openapi.json` - OpenAPI spec

### Basic Configuration

`application.yml`:
```yaml
openapi:
  enabled: true
  title: "My API"
  version: "1.0.0"
  description: "My awesome API built with Mitsuki"
```


## Configuration

### Full Configuration Options

`application.yml`:
```yaml
openapi:
  enabled: true                    # Enable/disable OpenAPI generation

  # API Metadata
  title: "My API"
  version: "1.0.0"
  description: "Comprehensive API documentation"

  # Contact Information
  contact:
    name: "API Support"
    email: "support@example.com"
    url: "https://example.com/support"

  # License
  license:
    name: "Apache 2.0"
    url: "https://www.apache.org/licenses/LICENSE-2.0.html"

  # Server Information
  server:
    url: "https://api.example.com"
    description: "Production server"

  # UI Configuration
  ui:
    - swagger                       # Enable Swagger UI at /swagger
    - redoc                         # Enable ReDoc at /redoc
    - scalar                        # Enable Scalar at /scalar

  docs_ui: scalar                   # Which UI to serve at /docs
  docs_url: /docs                   # Path for main docs
  openapi_url: /openapi.json        # Path for OpenAPI spec
```

### Configuration Defaults

From `mitsuki/config/defaults.yml`:
```yaml
openapi:
  enabled: true
  ui:
    - swagger
  docs_ui: scalar
  title: "Mitsuki API"
  version: "1.0.0"
  description: ""
  docs_url: /docs
  openapi_url: /openapi.json
```

### Environment Variables

Override configuration via environment:
```bash
MITSUKI_OPENAPI_ENABLED=true
MITSUKI_OPENAPI_TITLE="My API"
MITSUKI_OPENAPI_VERSION="2.0.0"
```


## Multiple UIs

Mitsuki supports three OpenAPI UI renderers simultaneously.

### Enabling Multiple UIs

`application.yml`:
```yaml
openapi:
  ui:
    - swagger
    - redoc
    - scalar
  docs_ui: scalar  # Preferred UI at /docs
```

**Access points:**
- `/docs` - Preferred UI (configured by `docs_ui`)
- `/swagger` - Swagger UI
- `/redoc` - ReDoc
- `/scalar` - Scalar

### Single UI Setup

Enable only one UI:
```yaml
openapi:
  ui:
    - scalar
  docs_ui: scalar
```

**Result:**
- `/docs` - Scalar UI
- `/scalar` - Scalar UI
- `/openapi.json` - OpenAPI spec


## Customizing Documentation

### Using Docstrings

```python
@RestController("/api/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: int) -> dict:
        """
        Get user by ID.

        Retrieves a single user record from the database
        using the provided user ID.
        """
        return {"id": id, "name": "John"}
```

Docstrings automatically become operation descriptions.

### Typed Responses

Use type hints for automatic schema generation:

```python
from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str

@RestController("/api/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: int) -> User:
        """Get user by ID."""
        return User(id=id, name="John", email="john@example.com")
```

OpenAPI will automatically generate a `User` schema.


## Decorators

### @OpenAPIOperation

Add detailed operation metadata.

```python
from mitsuki import GetMapping, RestController
from mitsuki.openapi import OpenAPIOperation

@RestController("/api/users")
class UserController:
    @GetMapping("/{id}")
    @OpenAPIOperation(
        summary="Get user by ID",
        description="Retrieve a single user by their unique identifier",
        tags=["Users", "Management"],
        responses={
            404: {"description": "User not found"},
            500: {"description": "Internal server error"}
        },
        deprecated=False
    )
    async def get_user(self, id: int):
        return {"id": id, "name": "John"}
```

**Parameters:**
- `summary` - Brief operation summary
- `description` - Detailed description
- `tags` - List of tags for grouping
- `responses` - Custom response definitions
- `parameters` - Additional parameter docs
- `deprecated` - Mark as deprecated
- `operation_id` - Custom operation ID

### @OpenAPITag

Add tag metadata to controllers.

```python
from mitsuki import RestController
from mitsuki.openapi import OpenAPITag

@RestController("/api/users")
@OpenAPITag(
    name="Users",
    description="User management and authentication",
    external_docs={
        "description": "User API Guide",
        "url": "https://docs.example.com/users"
    }
)
class UserController:
    pass
```

**Parameters:**
- `name` - Tag name
- `description` - Tag description
- `external_docs` - Link to external documentation

### @OpenAPISecurity

Specify security requirements.

```python
from mitsuki import GetMapping
from mitsuki.openapi import OpenAPISecurity

@GetMapping("/protected")
@OpenAPISecurity(["bearerAuth"])
async def protected_endpoint(self):
    return {"data": "sensitive"}
```

**Parameters:**
- `schemes` - List of security scheme names


## Schema Generation

### Automatic Type Inference

Mitsuki automatically generates schemas from:
- Dataclasses
- Enums
- Type hints
- Nested objects

**Example:**

```python
from dataclasses import dataclass
from enum import Enum

class Status(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

@dataclass
class Address:
    street: str
    city: str
    country: str

@dataclass
class User:
    name: str
    email: str
    status: Status
    address: Address

@RestController("/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: int) -> User:
        return User(
            name="John",
            email="john@example.com",
            status=Status.ACTIVE,
            address=Address("123 Main", "NYC", "USA")
        )
```

**Generated OpenAPI schema:**
```json
{
  "User": {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "email": {"type": "string"},
      "status": {
        "type": "string",
        "enum": ["active", "inactive"]
      },
      "address": {"$ref": "#/components/schemas/Address"}
    }
  },
  "Address": {
    "type": "object",
    "properties": {
      "street": {"type": "string"},
      "city": {"type": "string"},
      "country": {"type": "string"}
    }
  }
}
```

### Request Body Schemas

```python
@dataclass
class CreateUserRequest:
    name: str
    email: str
    status: Status

@RestController("/users")
class UserController:
    @PostMapping("/")
    async def create_user(self, request: CreateUserRequest) -> User:
        """Create a new user."""
        return User(
            name=request.name,
            email=request.email,
            status=request.status,
            address=Address("", "", "")
        )
```

Request body schema is automatically inferred from `CreateUserRequest`.

### Custom Response Schemas

```python
@GetMapping("/custom")
@OpenAPIOperation(
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                            "timestamp": {"type": "string"}
                        }
                    }
                }
            }
        }
    }
)
async def custom_response(self):
    return {"message": "Hello", "timestamp": "2024-01-01T00:00:00Z"}
```


## Security Schemes

### Defining Security Schemes

Currently, security schemes must be configured in code or via configuration providers. Future versions will support YAML-based security scheme definitions.

**Common security schemes:**

**Bearer Token (JWT):**
```python
from mitsuki import Configuration, Provider

@Configuration
class OpenAPIConfig:
    @Provider
    def security_schemes(self):
        return {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            }
        }
```

**API Key:**
```python
@Provider
def security_schemes(self):
    return {
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
```

**OAuth2:**
```python
@Provider
def security_schemes(self):
    return {
        "oauth2": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "https://example.com/oauth/authorize",
                    "tokenUrl": "https://example.com/oauth/token",
                    "scopes": {
                        "read": "Read access",
                        "write": "Write access"
                    }
                }
            }
        }
    }
```

### Applying OpenAPI Security to Endpoints

To apply blockage over an endpoint in the OpenAPI UIs, annotate the route mapping with `@OpenAPISecurity`:

```python
from mitsuki.openapi import OpenAPISecurity

@RestController("/api/protected")
class ProtectedController:
    @GetMapping("/data")
    @OpenAPISecurity(["bearerAuth"])
    async def get_data(self):
        return {"secret": "data"}
```

This, of course, is just for the UI, and provides users with a visual (i.e. lock icon) and interactive way (i.e. "Authorize" button) to provide their security tokens over the UI.


## Best Practices

### 1. Use Type Hints

Always specify return types for automatic schema generation:

```python
@GetMapping("/{id}")
async def get_user(self, id: int) -> User:  # Type hint provided
    ...
```

### 2. Write Clear Docstrings

First line becomes the summary, rest becomes description:

```python
@GetMapping("/{id}")
async def get_user(self, id: int) -> User:
    """
    Get user by ID.

    Retrieves a single user from the database using their unique identifier.
    Returns 404 if user not found.
    """
    ...
```

### 3. Group Related Endpoints with Tags

```python
@RestController("/api/users")
@OpenAPITag(name="User Management", description="CRUD operations for users")
class UserController:
    ...

@RestController("/api/auth")
@OpenAPITag(name="Authentication", description="Login and token management")
class AuthController:
    ...
```

### 4. Document Error Responses

```python
@GetMapping("/{id}")
@OpenAPIOperation(
    responses={
        404: {"description": "User not found"},
        403: {"description": "Access denied"},
        500: {"description": "Internal server error"}
    }
)
async def get_user(self, id: int) -> User:
    ...
```

### 5. Use Dataclasses for Complex Types

```python
@dataclass
class CreateUserRequest:
    name: str
    email: str
    password: str

@PostMapping("/")
async def create_user(self, request: CreateUserRequest) -> User:
    ...
```

### 6. Disable in Production (Optional)

For security-sensitive APIs:

```yaml
# application-production.yml
openapi:
  enabled: false
```

### 7. Customize Per Environment

```yaml
# application-development.yml
openapi:
  enabled: true
  ui:
    - swagger
    - redoc
    - scalar

# application-production.yml
openapi:
  enabled: true
  ui:
    - redoc  # Only ReDoc in production
  server:
    url: "https://api.production.com"
```


## Complete Example

```python
from dataclasses import dataclass
from enum import Enum
from mitsuki import Application, RestController, GetMapping, PostMapping
from mitsuki.openapi import OpenAPIOperation, OpenAPITag, OpenAPISecurity

class Status(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

@dataclass
class User:
    id: int
    name: str
    email: str
    status: Status

@dataclass
class CreateUserRequest:
    name: str
    email: str

@RestController("/api/users")
@OpenAPITag(
    name="Users",
    description="User management endpoints",
    external_docs={
        "description": "User Guide",
        "url": "https://docs.example.com/users"
    }
)
class UserController:
    @GetMapping("/{id}")
    @OpenAPIOperation(
        summary="Get user by ID",
        description="Retrieve a single user by unique identifier",
        tags=["Users"],
        responses={
            404: {"description": "User not found"}
        }
    )
    async def get_user(self, id: int) -> User:
        """Get user by ID."""
        return User(id=id, name="John", email="john@example.com", status=Status.ACTIVE)

    @PostMapping("/")
    @OpenAPIOperation(
        summary="Create new user",
        description="Create a new user account",
        tags=["Users"]
    )
    @OpenAPISecurity(["bearerAuth"])
    async def create_user(self, request: CreateUserRequest) -> User:
        """Create a new user."""
        return User(
            id=1,
            name=request.name,
            email=request.email,
            status=Status.ACTIVE
        )

@Application
class MyApp:
    pass

if __name__ == "__main__":
    MyApp.run()
```

**application.yml:**
```yaml
openapi:
  enabled: true
  title: "User Management API"
  version: "1.0.0"
  description: "API for managing users"
  ui:
    - swagger
    - redoc
    - scalar
  docs_ui: scalar
  contact:
    name: "API Team"
    email: "api@example.com"
```

**Access points:**
- `http://localhost:8000/docs` - Scalar UI
- `http://localhost:8000/swagger` - Swagger UI
- `http://localhost:8000/redoc` - ReDoc
- `http://localhost:8000/openapi.json` - OpenAPI spec


## Next Steps

- [Controllers](./04_controllers.md) - Learn about request handling
- [Request/Response Validation](./10_request_response_validation.md) - Data validation
- [JSON Serialization](./11_json_serialization.md) - Complex type handling
- [Configuration](./06_configuration.md) - Environment-specific settings
