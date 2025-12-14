# Controllers & Request Handling

## Table of Contents

- [Overview](#overview)
- [Controller Types](#controller-types)
- [Request Mapping](#request-mapping)
- [Path Variables](#path-variables)
- [Query Parameters](#query-parameters)
- [Request Body](#request-body)
- [Response Handling](#response-handling)
- [Complete Examples](#complete-examples)

## Overview

Mitsuki controllers handle HTTP requests and return responses. They provide:
- **Annotation-driven routing** - Map URLs to methods with decorators
- **Automatic JSON serialization** - Return dicts, lists, or dataclasses
- **Dependency injection** - Services injected via constructor
- **Async support** - All methods can be async
- **Path variables** - Extract values from URL paths
- **Query parameters** - Parse query strings
- **Request body parsing** - Automatic JSON deserialization
- **Request and response validation** - Automatic validation of incoming and outgoing objects, with support for excluding fields or enforcing types

## Controller Types

### @RestController

REST API controllers return JSON by default.

```python
from mitsuki import RestController, GetMapping

@RestController("/api/users")
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @GetMapping("")
    async def list_users(self) -> List[dict]:
        users = await self.service.get_all()
        return [{"id": u.id, "name": u.name} for u in users]
```

**Features:**
- Automatic JSON serialization of return values
- Content-Type: application/json header
- Perfect for REST APIs

### @Controller

Alias for @RestController - they're identical in Mitsuki.

```python
from mitsuki import Controller, GetMapping

@Controller("/api")  # Same as @RestController("/api")
class ApiController:
    @GetMapping("/health")
    async def health(self) -> dict:
        return {"status": "OK"}
```

## Request Mapping

### HTTP Method Decorators

Mitsuki provides decorators for all HTTP methods:

```python
from mitsuki import RestController, GetMapping, PostMapping, PutMapping
from mitsuki import PatchMapping, DeleteMapping

@RestController("/api/resources")
class ResourceController:
    @GetMapping("")
    async def list_resources(self):
        """GET /api/resources"""
        return []

    @PostMapping("")
    async def create_resource(self, body: dict):
        """POST /api/resources"""
        return {"id": 1}

    @GetMapping("/{id}")
    async def get_resource(self, id: str):
        """GET /api/resources/123"""
        return {"id": int(id)}

    @PutMapping("/{id}")
    async def update_resource(self, id: str, body: dict):
        """PUT /api/resources/123"""
        return {"success": True}

    @PatchMapping("/{id}")
    async def patch_resource(self, id: str, body: dict):
        """PATCH /api/resources/123"""
        return {"success": True}

    @DeleteMapping("/{id}")
    async def delete_resource(self, id: str):
        """DELETE /api/resources/123"""
        return {"success": True}
```

### Shorter Aliases

Mitsuki also provides shorter aliases for all mapping decorators:

```python
from mitsuki import RestController, Get, Post, Put, Patch, Delete

@RestController("/api/resources")
class ResourceController:
    @Get("")              # Same as @GetMapping("")
    async def list_resources(self):
        return []

    @Post("")             # Same as @PostMapping("")
    async def create(self, body: dict):
        return {"id": 1}

    @Put("/{id}")         # Same as @PutMapping("/{id}")
    async def update(self, id: str, body: dict):
        return {"success": True}

    @Patch("/{id}")       # Same as @PatchMapping("/{id}")
    async def patch(self, id: str, body: dict):
        return {"success": True}

    @Delete("/{id}")      # Same as @DeleteMapping("/{id}")
    async def delete(self, id: str):
        return {"success": True}
```

**Available aliases:**
- `@Get` = `@GetMapping`
- `@Post` = `@PostMapping`
- `@Put` = `@PutMapping`
- `@Patch` = `@PatchMapping`
- `@Delete` = `@DeleteMapping`

Both forms work identically and support all the same parameters.

### Path Composition

Paths are composed from controller + method:

```python
@RestController("/api/v1/users")  # Base path
class UserController:
    @GetMapping("")              # -> GET /api/v1/users
    @GetMapping("/{id}")         # -> GET /api/v1/users/{id}
    @GetMapping("/{id}/posts")   # -> GET /api/v1/users/{id}/posts
```

## Path Variables

Extract values from URL paths using `{variable}` syntax.

### Basic Path Variables

```python
@RestController("/api/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: str) -> dict:
        # GET /api/users/123 -> id = "123"
        user_id = int(id)
        user = await self.service.get_user(user_id)
        return {"id": user.id, "name": user.name}
```

**Type Conversion:** Mitsuki automatically converts path variables to the type specified in your method signature. If the conversion fails (e.g., providing "abc" for an `int`), it will result in a `400 Bad Request` error.

```python
# For a route like @GetMapping("/{id}")

# The 'id' parameter is automatically converted to an integer
async def get_user(self, id: int) -> dict:
    # GET /api/users/123 -> id = 123 (as an integer)
    user = await self.service.get_user(id)
    return {"id": user.id, "name": user.name}
```

### Multiple Path Variables

```python
@RestController("/api/posts")
class PostController:
    @GetMapping("/{post_id}/comments/{comment_id}")
    async def get_comment(self, post_id: str, comment_id: str) -> dict:
        # GET /api/posts/42/comments/7
        # post_id = "42", comment_id = "7"
        comment = await self.service.get_comment(
            int(post_id),
            int(comment_id)
        )
        return {"text": comment.text}
```

### Nested Resources

```python
@RestController("/api/organizations")
class OrgController:
    @GetMapping("/{org_id}/teams/{team_id}/members/{member_id}")
    async def get_member(
        self,
        org_id: str,
        team_id: str,
        member_id: str
    ) -> dict:
        # GET /api/organizations/1/teams/5/members/99
        return await self.service.get_member(
            int(org_id),
            int(team_id),
            int(member_id)
        )
```

## Query Parameters

Extract query string parameters using `@QueryParam`.

### Basic Query Parameters

```python
from mitsuki import QueryParam

@RestController("/api/users")
class UserController:
    @GetMapping("")
    async def search_users(
        self,
        q: str = QueryParam(default=""),
        page: int = QueryParam(default=0),
        size: int = QueryParam(default=10)
    ) -> List[dict]:
        # GET /api/users?q=john&page=2&size=20
        # q = "john", page = 2, size = 20
        users = await self.service.search(q, page, size)
        return [self._to_dict(u) for u in users]
```

### Query Parameter Types

Mitsuki automatically converts query parameters:

```python
@GetMapping("/filter")
async def filter_items(
    self,
    min_price: float = QueryParam(default=0.0),
    max_price: float = QueryParam(default=1000.0),
    in_stock: bool = QueryParam(default=True),
    category: str = QueryParam(default="all")
) -> List[dict]:
    # GET /filter?min_price=10.5&max_price=99.99&in_stock=true&category=electronics
    # min_price = 10.5 (float)
    # max_price = 99.99 (float)
    # in_stock = True (bool)
    # category = "electronics" (str)
    pass
```

### Complex Query Patterns

```python
@GetMapping("/search")
async def advanced_search(
    self,
    # Text search
    query: str = QueryParam(default=""),

    # Filters
    category: str = QueryParam(default="all"),
    min_price: float = QueryParam(default=0.0),
    max_price: float = QueryParam(default=float('inf')),

    # Pagination
    page: int = QueryParam(default=0),
    size: int = QueryParam(default=10),

    # Sorting
    sort_by: str = QueryParam(default="created_at"),
    sort_desc: bool = QueryParam(default=True)
) -> dict:
    # GET /search?query=laptop&category=electronics&min_price=500&max_price=2000&page=1&size=20&sort_by=price&sort_desc=false

    results = await self.service.search(
        query=query,
        filters={"category": category, "price_range": (min_price, max_price)},
        page=page,
        size=size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )

    return {
        "results": results,
        "page": page,
        "total": await self.service.count(query, filters)
    }
```

## Request Body

### Handling Request Bodies

POST, PUT, and PATCH methods can receive data in the request body. Mitsuki can automatically parse a JSON body into a Python dictionary or, for more robust validation, into a dataclass instance.

#### 1. Using a Dataclass (Recommended)

The best practice is to define a `dataclass` for your expected request payload and use it with the `RequestBody` parameter decorator. This provides automatic parsing and validation.

```python
from dataclasses import dataclass
from mitsuki import RestController, PostMapping, RequestBody, Consumes

@dataclass
class CreateUserRequest:
    name: str
    email: str
    age: int = 18 # With a default value

@RestController("/api/users")
class UserController:
    @PostMapping("")
    @Consumes(CreateUserRequest) # Specifies the type for validation
    async def create_user(self, user_data: CreateUserRequest = RequestBody()) -> dict:
        # Mitsuki automatically validates the request and injects a CreateUserRequest instance.
        # You can access attributes directly and safely.
        user = await self.service.create_user(
            name=user_data.name,
            email=user_data.email,
            age=user_data.age
        )
        return {"id": user.id, "name": user.name}
```
If the incoming JSON does not match the `CreateUserRequest` structure (e.g., missing fields, wrong types), Mitsuki will automatically return a `400 Bad Request` error. See the [Request/Response Validation](10_request_response_validation.md) guide for more details.

#### 2. Using a Dictionary

For simple cases without validation, you can have Mitsuki parse the body into a dictionary.

```python
@RestController("/api/users")
class UserController:
    @PostMapping("/simple")
    async def create_user_simple(self, body: dict) -> dict:
        # body is a dictionary parsed from the JSON request
        name = body.get("name")
        email = body.get("email")
        # Manual validation is required
        if not name or not email:
            return ResponseEntity.bad_request({"error": "Name and email are required"})

        user = await self.service.create_user(name, email)
        return {"id": user.id, "name": user.name}
```

### Combining Body and Path Variables

You can easily combine a request body with path variables.

```python
@PutMapping("/{id}")
@Consumes(UpdateUserRequest) # Assuming UpdateUserRequest is a dataclass
async def update_user(self, id: str, body: UpdateUserRequest = RequestBody()) -> dict:
    # PUT /api/users/123
    # Body: {"name": "Alice Updated"}

    user_id = int(id)
    updated = await self.service.update_user(user_id, updates=body)

    return {"success": True, "user": self._to_dict(updated)}
```

### Accessing the Raw Request

For use cases where you need direct access to the underlying request object (e.g., to read headers, access client information, or handle cookies), you can inject Starlette's `Request` object by simply adding it as a type-hinted parameter to your handler method.

This gives you control of the underlying `starlette.requests.Request` object:

```python
from mitsuki import RestController, GetMapping
from starlette.requests import Request

@RestController("/api/gateway")
class GatewayController:
    @GetMapping("/info")
    async def get_request_info(self, request: Request) -> dict:
        """
        Injects the Starlette Request object to access headers and client info.
        """
        return {
            "user_agent": request.headers.get("User-Agent", "Unknown"),
            "client_host": request.client.host,
            "client_port": request.client.port,
            "cookies": request.cookies,
            "path": request.url.path,
        }
```

This naturally works with other parameters like path variables, query parameters, and request bodies.

```python
@GetMapping("/users/{user_id}")
async def get_user_with_request(
    self,
    request: Request,
    user_id: int,
    q: str = QueryParam(default=None)
) -> dict:
    # You have access to the request, user_id, and q
    pass
```

## Response Handling

### JSON Responses (@RestController)

Return dictionaries, lists, or dataclasses:

```python
@RestController("/api/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: str) -> dict:
        user = await self.service.get_user(int(id))

        # Return dict - automatically serialized to JSON
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }

    @GetMapping("")
    async def list_users(self) -> List[dict]:
        users = await self.service.get_all()

        # Return list of dicts
        return [
            {"id": u.id, "name": u.name}
            for u in users
        ]
```

### Status Codes with ResponseEntity

For custom status codes and headers, use `ResponseEntity`:

```python
from mitsuki import ResponseEntity

@RestController("/api/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: int):
        user = await self.service.find_by_id(id)
        if not user:
            return ResponseEntity.not_found({"error": "User not found"})
        return user  # 200 OK by default

    @PostMapping("/")
    async def create_user(self, data: dict):
        user = await self.service.create(data)
        return ResponseEntity.created(user)  # 201 Created

    @DeleteMapping("/{id}")
    async def delete_user(self, id: int):
        await self.service.delete(id)
        return ResponseEntity.no_content()  # 204 No Content
```

**See [ResponseEntity](09_response_entity.md) for detailed documentation.**

### Error Responses

```python
@GetMapping("/{id}")
async def get_user(self, id: str) -> dict:
    try:
        user = await self.service.get_user(int(id))
        if not user:
            return {"error": "User not found"}, 404

        return {"id": user.id, "name": user.name}

    except ValueError:
        return {"error": "Invalid user ID"}, 400

    except Exception as e:
        return {"error": str(e)}, 500
```

### Plain Text Responses

```python
@RestController("/api")
class HealthController:
    @GetMapping("/health")
    async def health(self) -> str:
        # Return plain string - automatically converted to JSON string
        return "OK"

    @GetMapping("/version")
    async def version(self) -> dict:
        # Return structured data
        return {"version": "1.0.0", "status": "healthy"}
```

**Note:** For HTML rendering, consider using a frontend framework (React, Vue, etc.) with Mitsuki as the JSON API backend. 

## Complete Examples

### Simple CRUD API

```python
from mitsuki import RestController, GetMapping, PostMapping, PutMapping, DeleteMapping
from mitsuki import QueryParam, Service
from typing import List

@RestController("/api/users")
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @GetMapping("")
    async def list_users(
        self,
        page: int = QueryParam(default=0),
        size: int = QueryParam(default=10)
    ) -> List[dict]:
        """GET /api/users?page=0&size=10"""
        users = await self.service.get_all(page, size)
        return [self._to_dict(u) for u in users]

    @GetMapping("/{id}")
    async def get_user(self, id: str) -> dict:
        """GET /api/users/123"""
        user = await self.service.get_user(int(id))
        if not user:
            return {"error": "Not found"}, 404
        return self._to_dict(user)

    @PostMapping("")
    async def create_user(self, body: dict) -> dict:
        """POST /api/users"""
        if not body.get("email"):
            return {"error": "Email required"}, 400

        user = await self.service.create_user(
            name=body.get("name", ""),
            email=body["email"],
            age=body.get("age", 18)
        )
        return self._to_dict(user), 201

    @PutMapping("/{id}")
    async def update_user(self, id: str, body: dict) -> dict:
        """PUT /api/users/123"""
        user = await self.service.update_user(int(id), body)
        if not user:
            return {"error": "Not found"}, 404
        return self._to_dict(user)

    @DeleteMapping("/{id}")
    async def delete_user(self, id: str) -> dict:
        """DELETE /api/users/123"""
        success = await self.service.delete_user(int(id))
        if not success:
            return {"error": "Not found"}, 404
        return {"success": True}

    def _to_dict(self, user) -> dict:
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "age": user.age
        }
```

### Search & Filter API

```python
@RestController("/api/products")
class ProductController:
    def __init__(self, service: ProductService):
        self.service = service

    @GetMapping("/search")
    async def search(
        self,
        q: str = QueryParam(default=""),
        category: str = QueryParam(default=""),
        min_price: float = QueryParam(default=0.0),
        max_price: float = QueryParam(default=10000.0),
        in_stock: bool = QueryParam(default=None),
        page: int = QueryParam(default=0),
        size: int = QueryParam(default=20)
    ) -> dict:
        """
        GET /api/products/search?
            q=laptop&
            category=electronics&
            min_price=500&
            max_price=2000&
            in_stock=true&
            page=0&
            size=20
        """
        results = await self.service.search(
            query=q,
            category=category,
            price_range=(min_price, max_price),
            in_stock=in_stock,
            page=page,
            size=size
        )

        total = await self.service.count_results(
            query=q,
            category=category,
            price_range=(min_price, max_price),
            in_stock=in_stock
        )

        return {
            "results": [self._to_dict(p) for p in results],
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size
            }
        }

    def _to_dict(self, product) -> dict:
        return {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "category": product.category
        }
```

### Nested Resources

```python
@RestController("/api/posts")
class PostCommentController:
    def __init__(self, service: CommentService):
        self.service = service

    @GetMapping("/{post_id}/comments")
    async def list_comments(self, post_id: str) -> List[dict]:
        """GET /api/posts/42/comments"""
        comments = await self.service.get_comments_for_post(int(post_id))
        return [self._to_dict(c) for c in comments]

    @PostMapping("/{post_id}/comments")
    async def create_comment(self, post_id: str, body: dict) -> dict:
        """POST /api/posts/42/comments"""
        comment = await self.service.create_comment(
            post_id=int(post_id),
            text=body["text"],
            author=body["author"]
        )
        return self._to_dict(comment), 201

    @GetMapping("/{post_id}/comments/{comment_id}")
    async def get_comment(self, post_id: str, comment_id: str) -> dict:
        """GET /api/posts/42/comments/7"""
        comment = await self.service.get_comment(
            int(post_id),
            int(comment_id)
        )
        if not comment:
            return {"error": "Not found"}, 404
        return self._to_dict(comment)

    def _to_dict(self, comment) -> dict:
        return {
            "id": comment.id,
            "post_id": comment.post_id,
            "text": comment.text,
            "author": comment.author
        }
```


## Best Practices

1. **Keep controllers thin** - Business logic belongs in services
2. **Use type hints** - Mitsuki liberally relies on type hints for optional DX goodies


## Next Steps

- [Decorators](./02_decorators.md) - Complete decorator reference
- [Repositories](./03_repositories.md) - Data layer integration
- [Overview](./01_overview.md) - Architecture and design
