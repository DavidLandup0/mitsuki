# Request/Response Type Validation

Mitsuki provides simple but powerful request and response type validation. This allows you to:

- **Validate request data** against dataclass schemas
- **Validate response data** to ensure API consistency
- **Filter sensitive fields** from response output
- **Document API contracts** through type hints and DTOs
- **Ensure data consistency** across your API

## How Validation Works

Mitsuki validates request and response data automatically when you specify validation types. 
There are two equivalent ways to specify validation:

Decorator Approach
- **`@Produces(SomeDTO)`**: Validates and converts response data (output)
- **`@Consumes(SomeDTO)`**: Validates and converts request data (input)

Parameter Approach
- **`produces_type`** or **`return_type`**: Validates response data (on mapping decorators)
- **`consumes_type`**: Validates request data (on mapping decorators)
- **`exclude_fields`**: Removes specified fields from JSON output 

### Decorator Approach

Use `@Consumes` and `@Produces` decorators:

```python
from dataclasses import dataclass
from mitsuki import Controller, GetMapping, PostMapping, Consumes, Produces, RequestBody

@dataclass
class UserDTO:
    id: int
    username: str
    email: str

@dataclass
class CreateUserRequest:
    username: str
    email: str
    password: str

@Controller("/api/users")
class UserController:
    @GetMapping("/{id}")
    @Produces(UserDTO)
    async def get_user(self, id: int):
        return {"id": id, "username": "john", "email": "john@example.com"}

    @PostMapping("/")
    @Consumes(CreateUserRequest)
    @Produces(UserDTO)
    async def create_user(self, data: CreateUserRequest = RequestBody()):
        # data is a CreateUserRequest instance
        return UserDTO(id=1, username=data.username, email=data.email)
```

### Parameter Approach

Specify validation types as parameters on mapping decorators:

```python
@Controller("/api/users")
class UserController:
    @GetMapping("/{id}", produces_type=UserDTO)
    async def get_user(self, id: int):
        return {"id": id, "username": "john", "email": "john@example.com"}

    @PostMapping("/", consumes_type=CreateUserRequest, produces_type=UserDTO)
    async def create_user(self, data: CreateUserRequest = RequestBody()):
        return UserDTO(id=1, username=data.username, email=data.email)
```

**Both approaches are equivalent.** Use whichever you prefer:
- **Decorators**: More explicit, reads naturally ("this endpoint produces UserDTO")
- **Parameters**: More compact, all configuration in one place

**Note:** `produces_type` and `return_type` are aliases - they do the same thing.

## Output Validation

Output validation ensures your controller methods return data that conforms to a specified structure.

### What Happens

When you specify output validation, Mitsuki automatically:

1. **Validates the structure** - Checks that all required fields are present
2. **Type checks** - Ensures the return data matches the expected type
3. **Converts dataclasses** - If you return a dataclass instance, it's converted to a dict for JSON serialization
4. **Raises errors** - If validation fails, a clear error is raised

### Basic Usage

```python
from dataclasses import dataclass
from mitsuki import Controller, GetMapping

@dataclass
class UserDTO:
    id: int
    username: str
    email: str

@Controller("/api/users")
class UserController:
    @GetMapping("/{id}", produces_type=UserDTO)
    async def get_user(self, id: int):
        # This will be validated against UserDTO
        return {
            "id": id,
            "username": "john_doe",
            "email": "john@example.com"
        }
```

### Working with Lists

Output validation works with lists of objects:

```python
@dataclass
class PostDTO:
    id: int
    title: str
    content: str

@Controller("/api/posts")
class PostController:
    @GetMapping("/", produces_type=PostDTO)
    async def list_posts(self):
        # Returns list of posts, each validated against PostDTO
        return [
            {"id": 1, "title": "First Post", "content": "..."},
            {"id": 2, "title": "Second Post", "content": "..."}
        ]
```

### Validation Errors

If validation fails, a `RequestValidationException` is raised with details:

```python
@GetMapping("/{id}", produces_type=UserDTO)
async def get_user(self, id: int):
    # This will fail - missing 'email' field
    return {
        "id": id,
        "username": "john_doe"
    }
    # Raises: RequestValidationException("Failed to validate response against UserDTO: ...")
```

## Input Validation

Input validation ensures request data conforms to expected structures before processing.

### What Happens

When you specify input validation, request body data will be:

1. **Parsed from JSON** - Request body parsed to dict
2. **Validated** - Checked against dataclass schema
3. **Converted to instance** - Dict converted to dataclass instance
4. **Passed to handler** - Handler receives typed dataclass, not dict

### Basic Usage

```python
from dataclasses import dataclass
from mitsuki import Controller, PostMapping, RequestBody

@dataclass
class CreatePostRequest:
    title: str
    content: str
    author_id: int

@Controller("/api/posts")
class PostController:
    @PostMapping("/", consumes_type=CreatePostRequest)
    async def create_post(self, data: CreatePostRequest = RequestBody()):
        # data is a CreatePostRequest instance
        post = await self.service.create(
            title=data.title,
            content=data.content,
            author_id=data.author_id
        )
        return {"id": post.id, "title": post.title}
```

### Validation with Default Values

Dataclass default values are respected:

```python
@dataclass
class UpdatePostRequest:
    title: Optional[str] = None
    content: Optional[str] = None
    published: bool = False  # Default value

@PutMapping("/{id}", consumes_type=UpdatePostRequest)
async def update_post(self, id: int, data: UpdatePostRequest = RequestBody()):
    # If published not in request body, defaults to False
    ...
```

### Input Validation Errors

Invalid input raises clear `RequestValidationException` exceptions:

```python
# Request body: {"title": "Post Title"}  # Missing required 'content' field
# Raises: RequestValidationException("Failed to validate input against CreatePostRequest: ...")
```

### List Validation

Input validation works with lists of objects:

```python
@dataclass
class BatchUserRequest:
    users: List[CreateUserRequest]

@PostMapping("/batch", consumes_type=BatchUserRequest)
async def create_users_batch(self, data: BatchUserRequest = RequestBody()):
    # Each user in data.users is validated
    for user in data.users:
        await self.service.create(user)
```

## Field Exclusion

Field exclusion removes specified fields from your JSON response. This is useful for:

- **Hiding sensitive data** (passwords, tokens, internal IDs)
- **Reducing payload size** (removing unused fields)
- **Creating different views** (public vs admin endpoints)
- **API versioning** (deprecating fields gradually)

### Basic Usage

```python
from mitsuki import Controller, GetMapping

@Controller("/api/users")
class UserController:
    @GetMapping("/{id}", exclude_fields=["password_hash", "internal_id"])
    async def get_user(self, id: int):
        # password_hash and internal_id will be removed from output
        return {
            "id": id,
            "username": "john_doe",
            "email": "john@example.com",
            "password_hash": "hashed_password",
            "internal_id": "abc123"
        }
        # Client receives: {"id": 1, "username": "john_doe", "email": "john@example.com"}
```

### How It Works

Field exclusion is **recursive** - it removes fields at all nesting levels:

1. **Top-level fields** are removed
2. **Nested dictionaries** are processed recursively
3. **Lists of dictionaries** have fields removed from each item
4. **Deeply nested structures** are fully traversed

### Working with Nested Data

```python
@GetMapping("/posts", exclude_fields=["author_id", "views"])
async def get_posts(self):
    return {
        "posts": [
            {"id": 1, "title": "Post 1", "author_id": 10, "views": 100},
            {"id": 2, "title": "Post 2", "author_id": 20, "views": 200}
        ],
        "total": 2
    }
    # Output: {"posts": [{"id": 1, "title": "Post 1"}, {"id": 2, "title": "Post 2"}], "total": 2}
```

### Deeply Nested Structures

Field exclusion works at any depth:

```python
@GetMapping("/user/{id}/profile", exclude_fields=["password", "internal_notes"])
async def get_profile(self, id: int):
    return {
        "user": {
            "id": id,
            "name": "John",
            "password": "secret",
            "profile": {
                "bio": "Developer",
                "internal_notes": "VIP customer"
            }
        }
    }
    # Both 'password' and 'internal_notes' are removed at any depth
```

### Creating Public vs Admin Endpoints

A common pattern is to have different endpoints with different field visibility:

```python
@Controller("/api/posts")
class PostController:
    # Public endpoint - hides internal fields
    @GetMapping("/public", exclude_fields=["author_id", "views", "edit_token"])
    async def get_public_posts(self):
        posts = await self.post_service.get_all_posts()
        return [self._post_to_dict(p) for p in posts]

    # Admin endpoint - shows all fields
    @GetMapping("/admin")
    async def get_admin_posts(self):
        posts = await self.post_service.get_all_posts()
        return [self._post_to_dict(p) for p in posts]
```

## Combining Features

You can use validation and field exclusion together for maximum control:

```python
from dataclasses import dataclass
from mitsuki import Controller, GetMapping

@dataclass
class UserDTO:
    id: int
    username: str
    email: str
    password_hash: str
    internal_id: str
    last_login: str

@Controller("/api/users")
class UserController:
    @GetMapping(
        "/{id}",
        produces_type=UserDTO,
        exclude_fields=["password_hash", "internal_id"]
    )
    async def get_user(self, id: int):
        # Data is validated against UserDTO, then sensitive fields are removed
        return {
            "id": id,
            "username": "john_doe",
            "email": "john@example.com",
            "password_hash": "hashed_password",
            "internal_id": "abc123",
            "last_login": "2024-01-15T10:30:00"
        }
        # Client receives: {"id": 1, "username": "john_doe", "email": "john@example.com", "last_login": "..."}
```

### Processing Order

When both are specified, processing happens in this order:

1. **Validation** - Data is validated against `produces_type`
2. **Conversion** - Dataclasses are converted to dicts
3. **Filtering** - Fields in `exclude_fields` are removed

## Advanced Examples

### Example 1: Blog Post with Author Info

```python
from dataclasses import dataclass
from mitsuki import Controller, GetMapping

@dataclass
class PostDTO:
    id: int
    title: str
    content: str
    author_id: int
    author_name: str
    view_count: int
    internal_metrics: dict

@Controller("/api/posts")
class PostController:
    def __init__(self, post_service: PostService):
        self.post_service = post_service

    # Public endpoint - no sensitive fields
    @GetMapping(
        "/public",
        produces_type=PostDTO,
        exclude_fields=["author_id", "view_count", "internal_metrics"]
    )
    async def get_public_posts(self):
        posts = await self.post_service.get_published_posts()
        return [self._enrich_post(p) for p in posts]

    # Analytics endpoint - all fields visible
    @GetMapping("/analytics", produces_type=PostDTO)
    async def get_analytics_posts(self):
        posts = await self.post_service.get_all_posts()
        return [self._enrich_post(p) for p in posts]

    def _enrich_post(self, post):
        return PostDTO(
            id=post.id,
            title=post.title,
            content=post.content,
            author_id=post.author_id,
            author_name=post.author.username,
            view_count=post.views,
            internal_metrics={"score": 0.95, "quality": "high"}
        )
```

### Example 2: User Profile with Multiple Views

```python
@dataclass
class UserProfileDTO:
    id: int
    username: str
    email: str
    bio: str
    created_at: str
    last_login: str
    api_token: str
    admin_notes: str

@Controller("/api/users")
class UserController:
    # Self view - user sees their own data including token
    @GetMapping(
        "/me",
        produces_type=UserProfileDTO,
        exclude_fields=["admin_notes"]
    )
    async def get_my_profile(self, user_id: int):
        return await self._get_user_profile(user_id)

    # Public view - minimal info
    @GetMapping(
        "/{id}/public",
        produces_type=UserProfileDTO,
        exclude_fields=["email", "last_login", "api_token", "admin_notes"]
    )
    async def get_public_profile(self, id: int):
        return await self._get_user_profile(id)

    # Admin view - everything
    @GetMapping("/{id}/admin", produces_type=UserProfileDTO)
    async def get_admin_profile(self, id: int):
        return await self._get_user_profile(id)
```

### Example 3: Nested Comments with Privacy

```python
@dataclass
class CommentDTO:
    id: int
    content: str
    author_name: str
    author_email: str
    created_at: str
    ip_address: str
    is_flagged: bool

@Controller("/api/posts")
class PostController:
    @GetMapping(
        "/{id}/comments",
        produces_type=CommentDTO,
        exclude_fields=["author_email", "ip_address", "is_flagged"]
    )
    async def get_post_comments(self, id: int):
        comments = await self.comment_service.get_comments(id)
        return {
            "post_id": id,
            "comments": [self._comment_to_dto(c) for c in comments],
            "total": len(comments)
        }
        # Excluded fields are removed from nested comment objects
```

## Best Practices

### 1. Use DTOs for API Contracts

Define clear data transfer objects for your endpoints:

```python
@dataclass
class CreateUserRequest:
    username: str
    email: str
    password: str

@dataclass
class UserResponse:
    id: int
    username: str
    email: str
    created_at: str

@PostMapping("/", produces_type=UserResponse)
async def create_user(self, data: CreateUserRequest):
    # Type hints document your API
    user = await self.user_service.create(data)
    return UserResponse(...)
```

### 2. Consistent Field Exclusion

Define constants for commonly excluded fields:

```python
# constants.py
INTERNAL_FIELDS = ["internal_id", "admin_notes", "system_flags"]
SENSITIVE_FIELDS = ["password_hash", "api_token", "secret_key"]
ANALYTICS_FIELDS = ["view_count", "click_rate", "conversion_score"]

# controllers.py
@GetMapping("/public", exclude_fields=INTERNAL_FIELDS + SENSITIVE_FIELDS)
async def get_public_data(self):
    ...
```

### 3. Separate Public and Admin Endpoints

Don't mix public and admin access in the same endpoint:

```python
# Good - separate endpoints
@GetMapping("/public", exclude_fields=["sensitive_field"])
async def get_public_data(self): ...

@GetMapping("/admin")
async def get_admin_data(self): ...

# Bad - conditional logic in endpoint
@GetMapping("/data")
async def get_data(self, is_admin: bool):
    data = await self.service.get_data()
    if not is_admin:
        del data["sensitive_field"]  # Don't do this
    return data
```

### 4. Validate Early, Filter Late

Use `produces_type` for validation, `exclude_fields` for filtering:

```python
@GetMapping(
    "/users/{id}",
    produces_type=UserDTO,  # Validate structure
    exclude_fields=["password_hash"]  # Remove sensitive data
)
async def get_user(self, id: int):
    # Business logic here
    ...
```

### 5. Document Your DTOs

Add clear documentation to your data classes:

```python
@dataclass
class ProductDTO:
    """
    Product response DTO.

    Fields excluded in public endpoints:
    - cost_price: Internal pricing info
    - supplier_id: Internal supplier reference
    - margin: Profit margin percentage
    """
    id: int
    name: str
    price: float
    cost_price: float  # Excluded from public
    supplier_id: int   # Excluded from public
    margin: float      # Excluded from public
```

### 6. Test Your Validation

Write tests for validation and filtering:

```python
def test_user_response_validation():
    """Test that user response matches UserDTO."""
    response = client.get("/api/users/1")
    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "id" in data
    assert "username" in data

    # Verify excluded fields
    assert "password_hash" not in data
    assert "internal_id" not in data
```

### 7. Use with ResponseEntity

Combine validation/filtering with status codes:

```python
@GetMapping("/{id}", produces_type=UserDTO, exclude_fields=["password_hash"])
async def get_user(self, id: int):
    user = await self.user_service.get_user(id)
    if not user:
        return ResponseEntity.not_found({"error": "User not found"})

    return ResponseEntity.ok(self._user_to_dto(user))
```

## See Also

- [Controllers](04_controllers.md) - Controller basics and routing
- [Response Entity](09_response_entity.md) - HTTP response handling
- [Dependency Injection](03_dependency_injection.md) - Service injection
- [Database Queries](08_database_queries.md) - Working with repositories

## Summary

Mitsuki's request/response validation and field filtering provide:

- **Type safety** through validation
- **Privacy control** through `exclude_fields` filtering
- **API documentation** via type hints and DTOs
- **Flexible access levels** with different endpoint configurations

Use these features to build robust, secure APIs with clear contracts.
