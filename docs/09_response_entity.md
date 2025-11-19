# ResponseEntity

The `ResponseEntity` class provides a response builder for creating HTTP responses with custom status codes, headers, and body content.

## Overview

By default, controller methods that return a dictionary or list automatically get serialized to JSON with a 200 OK status. When you need more control over the HTTP response (status codes, headers, etc.), use `ResponseEntity`.

## Basic Usage

### Returning Data with Default 200 Status

```python
from mitsuki import RestController, GetMapping

@RestController("/api/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: int):
        user = {"id": id, "name": "John Doe"}
        return user  # Automatically 200 OK
```

### Using ResponseEntity for Custom Status Codes

```python
from mitsuki import RestController, GetMapping, PostMapping, ResponseEntity

@RestController("/api/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: int):
        user = await self.user_service.find_by_id(id)
        if not user:
            return ResponseEntity.not_found({"error": "User not found"})
        return ResponseEntity.ok(user)

    @PostMapping("/")
    async def create_user(self, data: dict):
        user = await self.user_service.create(data)
        return ResponseEntity.created(user)
```

## Static Factory Methods

ResponseEntity provides convenient static methods for common HTTP status codes:

### Success Responses

```python
# 200 OK
return ResponseEntity.ok({"message": "Success"})

# 201 Created
return ResponseEntity.created(new_resource)

# 202 Accepted
return ResponseEntity.accepted({"message": "Request accepted for processing"})

# 204 No Content
return ResponseEntity.no_content()
```

### Client Error Responses

```python
# 400 Bad Request
return ResponseEntity.bad_request({"error": "Invalid input"})

# 401 Unauthorized
return ResponseEntity.unauthorized({"error": "Authentication required"})

# 403 Forbidden
return ResponseEntity.forbidden({"error": "Access denied"})

# 404 Not Found
return ResponseEntity.not_found({"error": "Resource not found"})

# 409 Conflict
return ResponseEntity.conflict({"error": "Email already exists"})
```

### Server Error Responses

```python
# 500 Internal Server Error
return ResponseEntity.internal_server_error({"error": "Something went wrong"})
```

## Custom Status Codes

For status codes not covered by the static methods, use the builder pattern:

```python
# 418 I'm a teapot
return ResponseEntity.status(418).body({"message": "I'm a teapot"})

# 503 Service Unavailable
return ResponseEntity.status(503).body({"error": "Service temporarily unavailable"})
```

## Adding Headers

### Using the Builder Pattern

```python
@PostMapping("/")
async def create_user(self, data: dict):
    user = await self.user_service.create(data)

    return (
        ResponseEntity
        .status(201)
        .header("Location", f"/api/users/{user.id}")
        .header("X-Custom-Header", "custom-value")
        .body(user)
    )
```

### Using created() with Headers

For HATEOAS-style responses:

```python
@PostMapping("/")
async def create_user(self, data: dict):
    user = await self.user_service.create(data)

    return ResponseEntity.created(
        user,
        headers={"Location": f"/api/users/{user.id}"}
    )
```

### Using the header() Method

To add headers to a response:

```python
@GetMapping("/{id}")
async def get_user(self, id: int):
    user = await self.user_service.find_by_id(id)

    return (
        ResponseEntity
        .ok(user)
        .header("Cache-Control", "max-age=3600")
    )
```

## Complete Examples

### REST API with Full CRUD with ResponseEntity

```python
from mitsuki import RestController, GetMapping, PostMapping, PutMapping, DeleteMapping
from mitsuki import PathVariable, RequestBody, ResponseEntity

@RestController("/api/posts")
class PostController:
    def __init__(self, post_service: PostService):
        self.post_service = post_service

    @GetMapping("/")
    async def get_all_posts(self):
        posts = await self.post_service.find_all()
        return posts  # 200 OK by default

    @GetMapping("/{id}")
    async def get_post(self, id: int = PathVariable()):
        post = await self.post_service.find_by_id(id)
        if not post:
            return ResponseEntity.not_found({"error": "Post not found"})
        return post

    @PostMapping("/")
    async def create_post(self, data: dict = RequestBody()):
        post = await self.post_service.create(data)
        return ResponseEntity.created(
            post,
            headers={"Location": f"/api/posts/{post.id}"}
        )

    @PutMapping("/{id}")
    async def update_post(self, id: int = PathVariable(), data: dict = RequestBody()):
        existing = await self.post_service.find_by_id(id)
        if not existing:
            return ResponseEntity.not_found({"error": "Post not found"})

        updated = await self.post_service.update(id, data)
        return ResponseEntity.ok(updated)

    @DeleteMapping("/{id}")
    async def delete_post(self, id: int = PathVariable()):
        success = await self.post_service.delete(id)
        if not success:
            return ResponseEntity.not_found({"error": "Post not found"})
        return ResponseEntity.no_content()
```

### Validation with Error Responses

```python
@PostMapping("/")
async def create_user(self, data: dict = RequestBody()):
    # Validation
    if not data.get("email"):
        return ResponseEntity.bad_request({
            "error": "Validation failed",
            "details": {"email": "Email is required"}
        })

    # Check for duplicates
    existing = await self.user_service.find_by_email(data["email"])
    if existing:
        return ResponseEntity.conflict({
            "error": "Email already exists"
        })

    # Create user
    user = await self.user_service.create(data)
    return ResponseEntity.created(user)
```

### Custom Status Code Example

```python
@GetMapping("/health")
async def health_check(self):
    # Custom health check logic
    if not await self.check_database():
        return ResponseEntity.status(503).body({
            "status": "unhealthy",
            "reason": "Database unavailable"
        })

    return ResponseEntity.ok({
        "status": "healthy",
        "uptime": self.get_uptime()
    })
```

## Aliases

ResponseEntity has two aliases for developers who prefer different naming conventions:

```python
from mitsuki import ResponseEntity
from mitsuki import JsonResponse    # Alternative
from mitsuki import JSONResponse    # Alternative

# All three are the same class
return ResponseEntity.ok(data)
return JsonResponse.ok(data)
return JSONResponse.ok(data)
```

## Content Type Handling

ResponseEntity automatically sets the `Content-Type` header based on the response body:

- `dict` or `list` → `application/json`
- `str` → `text/plain; charset=utf-8`
- `bytes` → `application/octet-stream`
- `None` → `application/json` (empty body)

You can override the content type by setting a custom header:

```python
return (
    ResponseEntity
    .ok(xml_string)
    .header("Content-Type", "application/xml")
)
```

## See Also

- [Controllers](04_controllers.md) - REST API controllers and routing
- [Database Queries](08_database_queries.md) - Custom queries with @Query decorator
