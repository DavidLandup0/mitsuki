# Decorators Reference

## Table of Contents

- [Component Decorators](#component-decorators)
- [Web Decorators](#web-decorators)
- [Data Layer Decorators](#data-layer-decorators)
- [Configuration Decorators](#configuration-decorators)

## Component Decorators

### @Component

Generic component decorator. Marks a class as a managed component in the DI container.

```python
from mitsuki import Component

@Component()
class CacheManager:
    def __init__(self):
        self.cache = {}
```

**Parameters:**
- `name` (optional): Custom name for the component. Defaults to class name.
- `scope` (optional): `Scope.SINGLETON` (default) or `Scope.PROTOTYPE`. String values `"singleton"` and `"prototype"` also accepted.

**When to use:**
- For utility classes that don't fit `@Service` or `@Repository`
- Infrastructure components (cache, event bus, etc.)
- Generic helpers

### @Service

Service layer component decorator. Semantically indicates business logic layer.

```python
from mitsuki import Service

@Service()
class UserService:
    def __init__(self, user_repo: UserRepository):
        self.repo = user_repo

    async def create_user(self, name: str) -> User:
        # Business logic here
        return await self.repo.save(User(name=name))
```

**Parameters:**
- `name` (optional): Custom name for the service
- `scope` (optional): `Scope.SINGLETON` (default) or `Scope.PROTOTYPE`. String values also accepted.

### @Repository

Data access layer component decorator. Marks a class as a repository for data operations.

```python
from mitsuki import Repository

@Repository()
class UserRepository:
    async def find_by_email(self, email: str) -> Optional[User]:
        pass
```

**Parameters:**
- `name` (optional): Custom name for the repository
- `scope` (optional): `Scope.SINGLETON` (default) or `Scope.PROTOTYPE`. String values also accepted.

**When to use:**
- For custom repository implementations
- When you need manual database access
- When `@CrudRepository` doesn't meet your needs

**See also:** [@CrudRepository](#crudrepository) for auto-implemented repositories

## Web Decorators

### @RestController

Web controller decorator for handling HTTP requests.

```python
from mitsuki import RestController, GetMapping

@RestController("/api/users")
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @GetMapping("/{id}")
    async def get_user(self, id: str) -> dict:
        user = await self.service.get_user(int(id))
        return {"id": user.id, "name": user.name}
```

**Parameters:**
- `path`: Base URL path for all routes in this controller

**Features:**
- Automatic JSON serialization
- Path prefix for all methods

**Aliases:**
All of these are identical in Mitsuki:
```python
from mitsuki import RestController, Controller, RestRouter, Router

@RestController("/api")  # Primary name
@Controller("/api")      # Alias
@RestRouter("/api")      # Alias
@Router("/api")          # Alias
```

**Note:** In Mitsuki, there is no distinction between @Controller and @RestController - they all behave the same way. Use whichever name you prefer.

### @GetMapping

Maps HTTP GET requests to controller methods.

```python
@GetMapping("/users")
async def list_users(self) -> List[dict]:
    return await self.service.get_all()

@GetMapping("/users/{id}")
async def get_user(self, id: str) -> dict:
    return await self.service.get_by_id(int(id))
```

**Parameters:**
- `path`: URL pattern (supports path variables with `{name}` syntax)

**Path variables:**
```python
@GetMapping("/posts/{post_id}/comments/{comment_id}")
async def get_comment(self, post_id: str, comment_id: str) -> dict:
    # Path variables passed as method parameters
    pass
```

### @PostMapping

Maps HTTP POST requests to controller methods.

```python
@PostMapping("/users")
async def create_user(self, body: dict) -> dict:
    user = await self.service.create(body["name"], body["email"])
    return {"id": user.id}
```

**Parameters:**
- `path`: URL pattern

**Request body:**

A dictionary or `RequestBody`:

```python
async def create_user(self, body: dict) -> dict:
    # body contains parsed JSON from request
    name = body.get("name")
    email = body.get("email")
```

**Aliases:**
These are identical in Mitsuki:

```python
from mitsuki import PostMapping, Post

@PostMapping("/api")  # Primary name
@Post("/api") # Alias
```

### @PutMapping

Maps HTTP PUT requests to controller methods (full updates).

```python
@PutMapping("/users/{id}")
async def update_user(self, id: str, body: dict) -> dict:
    user = await self.service.update(int(id), body)
    return {"success": True}
```

**Aliases:**
These are identical in Mitsuki:

```python
from mitsuki import PutMapping, Put

@PutMapping("/api")  # Primary name
@Put("/api") # Alias
```

### @PatchMapping

Maps HTTP PATCH requests to controller methods (partial updates).

```python
@PatchMapping("/users/{id}")
async def patch_user(self, id: str, body: dict) -> dict:
    user = await self.service.patch(int(id), body)
    return {"success": True}
```

**Aliases:**
These are identical in Mitsuki:

```python
from mitsuki import PatchMapping, Patch

@PatchMapping("/api")  # Primary name
@Patch("/api") # Alias
```

### @DeleteMapping

Maps HTTP DELETE requests to controller methods.

```python
@DeleteMapping("/users/{id}")
async def delete_user(self, id: str) -> dict:
    await self.service.delete(int(id))
    return {"success": True}
```

**Aliases:**
These are identical in Mitsuki:

```python
from mitsuki import DeleteMapping, Delete

@DeleteMapping("/api")  # Primary name
@Delete("/api") # Alias
```

### @QueryParam

Extracts query parameters from the request URL.

```python
from mitsuki import QueryParam

@GetMapping("/users")
async def search_users(
    self,
    q: str = QueryParam(default=""),
    page: int = QueryParam(default=0),
    size: int = QueryParam(default=10)
) -> List[dict]:
    # GET /users?q=john&page=2&size=20
    return await self.service.search(q, page, size)
```

**Parameters:**
- `default`: Default value if parameter not provided

## Data Layer Decorators

### @Entity

Marks a dataclass as a database entity.

```python
from mitsuki import Entity, Id, Column
from dataclasses import dataclass

@Entity()
@dataclass
class User:
    id: int = Id()
    name: str = ""
    email: str = Column(unique=True, default="")
    age: int = 0
```

**Features:**
- Auto-generates database table
- Field metadata for constraints
- Works with `@CrudRepository`

**Must be used with `@dataclass`**

### @CrudRepository

Auto-implements CRUD repository for an entity.

```python
from mitsuki import CrudRepository

@CrudRepository(entity=User)
class UserRepository:
    # Built-in methods (no implementation needed):
    # - save(entity) -> Entity
    # - find_by_id(id) -> Optional[Entity]
    # - find_all(page, size, sort_by, sort_desc) -> List[Entity]
    # - delete(entity) -> None
    # - delete_by_id(id) -> None
    # - count() -> int
    # - exists_by_id(id) -> bool

    # Dynamic query DSL (auto-implemented):
    async def find_by_email(self, email: str) -> Optional[User]: ...
    async def find_by_age_greater_than(self, age: int) -> List[User]: ...
    async def count_by_active(self, active: bool) -> int: ...
```

**Parameters:**
- `entity`: The entity class this repository manages

**See:** [Repositories Guide](./repositories.md) for complete DSL reference, custom queries, and SQLAlchemy engine support

### Field Decorators

#### Id()

Marks a field as the primary key.

```python
@dataclass
class User:
    id: int = Id()  # Auto-incrementing primary key
```


#### Column()

Provides metadata for database columns.

```python
from mitsuki import Column

@dataclass
class User:
    email: str = Column(unique=True, default="")
    name: str = Column(nullable=False, default="")
    bio: str = Column(default="", max_length=500)
```

**Parameters:**
- `unique`: Create unique constraint
- `nullable`: Allow NULL values
- `default`: Default value
- `max_length`: Maximum length (for strings)
- `index`: Create index on column

## Configuration Decorators

### @Configuration

Marks a class as a configuration source for providers.

```python
from mitsuki import Configuration, Provider, Value

@Configuration
class AppConfig:
    timeout: int = Value("${http.timeout:30}")

    @Provider
    def http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout)
```

**Features:**
- Can contain `@Value` fields
- Can have `@Provider` factory methods
- Can be combined with `@Profile`
- Dependencies can be injected into a constructor

Any `@Provider` can be injected into a constructor, making this a simple way to centrally configure factory methods.
I.e. any component that performs:

```python
@Service
class UserService:
    def __init__(self, http_client):
        self.client = http_client # <-- This is the http_client()-configured object from before
```

### @Provider

Marks a method in a `@Configuration` class as a provider factory method.

```python
@Configuration
class DatabaseConfig:
    @Provider
    def connection_pool(self) -> ConnectionPool:
        return ConnectionPool(size=10, timeout=30)

    @Provider(name="redis_client", scope="singleton")
    def create_redis(self) -> Redis:
        return Redis(host="localhost")
```

**Parameters:**
- `name` (optional): Custom provider name. Defaults to method name.
- `scope` (optional): `Scope.SINGLETON` (default) or `Scope.PROTOTYPE`. String values also accepted.

**Can be used with or without parentheses:**
```python
@Provider
def my_provider(self): ...

@Provider()
def my_provider(self): ...

@Provider(name="custom")
def my_provider(self): ...
```

**See:** [Overview](./overview.md#dependency-injection) for provider injection details.

### @Value

Injects configuration values into class properties.

```python
from mitsuki import Value, Configuration

@Configuration
class AppConfig:
    # From application.yml
    port: int = Value("${server.port:8000}")
    app_name: str = Value("${app.name}")

    # With default value
    debug: bool = Value("${app.debug:false}")
```

**Syntax:**
- `"${key}"` - Get value for key, `None` if not found
- `"${key:default}"` - Get value for key, use default if not found

**Environment variables:**
```bash
MITSUKI_DATABASE_URL=postgresql://localhost/db
```

Pattern: `MITSUKI_` + `KEY_IN_UPPERCASE_WITH_UNDERSCORES`.
`SERVER_SOMETHING` is equivalent to `server.something`.

### @Profile

Conditional component registration based on active environment.

```python
from mitsuki import Configuration, Profile, Provider

@Configuration
@Profile("development")
class DevConfig:
    @Provider
    def database_url(self) -> str:
        return "sqlite:///dev.db"

@Configuration
@Profile("production")
class ProdConfig:
    @Provider
    def database_url(self) -> str:
        return "postgresql://prod-server/db"
```

**Parameters:**
- `*profiles`: One or more profile names. Component is active if any match.

**Multiple profiles:**
```python
@Profile("development", "test")  # Active in dev OR test
class SharedConfig:
    pass
```

**Set active profile:**
```bash
MITSUKI_PROFILE=production python app.py
```

**See:** [Profiles Guide](./profiles.md) for complete documentation

### @Application

Main application entry point decorator.

```python
from mitsuki import Application, Value

@Application
class MyApp:
    # Can use @Value for configuration
    port: int = Value("${server.port:8000}")

    # Can have @Provider methods
    @Provider
    def some_provider(self):
        return SomeService()

if __name__ == "__main__":
    MyApp.run()  # Start the application
```

**Features:**
- Automatically treated as `@Configuration`
- Provides `run()` class methods
- Triggers application startup

## Decorator Combinations

### Common Patterns

**Service with injected repository:**

```python
@Service()
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo
```

**Controller with injected service:**
```python
@RestController("/api/users")
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @GetMapping("/{id}")
    async def get_user(self, id: str) -> dict:
        ...
```

**Profile-specific configuration:**
```python
@Configuration
@Profile("production")
class ProdConfig:
    @Provider
    def cache(self) -> Redis:
        return Redis(host="prod-redis")
```

**Entity with repository:**
```python
@Entity()
@dataclass
class User:
    id: int = Id()
    name: str = ""

@CrudRepository(entity=User)
class UserRepository:
    async def find_by_name(self, name: str) -> List[User]: ...
```

## Scopes

All component decorators support scope configuration using the `Scope` enum (or string value).

```python
from mitsuki.core.enums import Scope
```

### Scope.SINGLETON (default)

One instance per container. Created once and reused.

```python
from mitsuki.core.enums import Scope

@Service(scope=Scope.SINGLETON)  # or just @Service()
class ConfigService:
    pass

@Provider(scope=Scope.SINGLETON) # or scope='singleton'
def database_pool(self):
    return Pool()
```

**When to use:**
- If components are stateless
- Shared resources (connection pools, caches)
- Configuration objects

### Scope.PROTOTYPE

New instance created on each injection.

```python
from mitsuki.core.enums import Scope

@Service(scope=Scope.PROTOTYPE)
class RequestHandler:
    pass

@Provider(scope=Scope.PROTOTYPE)
def temp_file(self):
    return TempFile()
```

**Note on Provider Scopes:** Currently, all `@Provider` methods behave as singletons, regardless of the specified scope. The factory method is only run once, and its result is cached and reused for all subsequent injections. True prototype behavior for providers is not yet fully implemented.

**When to use:**
- When components are stateful
- Per-request resources
- Objects with lifecycle tied to specific operations

**String values:** You can also use string values `"singleton"` or `"prototype"` which are automatically converted to the enum.

## Next Steps

- [Overview](./01_overview.md) - Framework architecture and concepts
- [Repositories](./03_repositories.md) - Data layer and query DSL
- [Controllers](./04_controllers.md) - Web layer and request handling
- [Profiles](./05_profiles.md) - Environment-specific configuration
