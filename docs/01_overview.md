# Mitsuki Framework Overview

Mitsuki brings Spring Boot's proven architectural patterns to Python, combining:
- **Enterprise patterns** - Battle-tested architectural layering, dependency injection and inversion of control
- **Python productivity** - Fast development with clean, expressive syntax
- **Modern async** - Built on ASGI for high-performance, scalable applications

## Core Concepts

### Inversion of Control (IoC)

IoC is a design principle where the framework controls the flow of the application, rather than the application controlling the framework. Instead of manually creating and managing objects, you declare what you need and let Mitsuki handle the lifecycle.

**Traditional approach (no IoC):**
```python
class UserService:
    def __init__(self):
        self.repo = UserRepository()  # Tight coupling
        self.email = EmailService()

class UserController:
    def __init__(self):
        self.service = UserService()  # Manual creation
```

**Mitsuki approach (with IoC):**
```python
@Service
class UserService:
    def __init__(self, repo: UserRepository, email: EmailService):
        # Mitsuki injects dependencies automatically
        self.repo = repo
        self.email = email

@RestController("/users")
class UserController:
    def __init__(self, service: UserService):
        # Mitsuki creates and injects UserService
        self.service = service
```

### Dependency Injection (DI)

DI is the mechanism that implements IoC. Mitsuki automatically:
1. Discovers components via decorators (`@Service`, `@Repository`, etc.)
2. Analyzes constructor parameters and type hints
3. Resolves and injects dependencies
4. Manages component lifecycle (singleton vs prototype)

**Benefits:**
- **Loose coupling** - Components don’t construct their own dependencies, and can rely on abstractions when desired
- **Testability** - Easy to mock dependencies in unit tests
- **Maintainability** - Clear separation of concerns

### The Container

The DI Container is the heart of Mitsuki. It:
- Stores component metadata (type, name, scope, dependencies)
- Resolves dependency graphs
- Creates and caches instances (for singletons)
- Detects circular dependencies
- Provides providers to the application

**Component Registration:**

Components are registered when decorators are applied (import-time):

```python
from mitsuki import Service, Repository, RestController

@Repository()  # Registered immediately
class UserRepository:
    pass

@Service()  # Registered immediately
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

@RestController("/api")  # Registered immediately
class ApiController:
    def __init__(self, service: UserService):
        self.service = service
```

**Dependency Resolution:**

When Mitsuki starts, it:
1. Scans all registered components
2. For each component, resolves its dependencies
3. Creates instances in the correct order (dependencies first)

```
Container Resolution Order:
1. UserRepository (no dependencies) → create instance
2. UserService (depends on UserRepository) → inject UserRepository → create instance
3. ApiController (depends on UserService) → inject UserService → create instance
```

## Architecture Layers

Mitsuki encourages a layered architecture, where each layer has clearly defined scope and responsibilities, where lower layers (i.e. closer to data layer) don't depend on layers above:

```
┌─────────────────────────────────┐
│   Presentation Layer            │  @RestController, @Controller
│   (Controllers, Web)            │  Handle HTTP requests/responses
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│   Business Logic Layer          │  @Service
│   (Services)                    │  Application logic, orchestration
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│   Data Access Layer             │  @Repository, @CrudRepository
│   (Repositories)                │  Database operations, queries
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│   Domain Layer                  │  @Entity
│   (Entities, Models)            │  Business objects, data models
└─────────────────────────────────┘
```

**Example flow:**

```python
# Domain Layer
@Entity()
@dataclass
class User:
    id: int = Id()
    name: str = ""
    email: str = Column(unique=True, default="")

# Data Access Layer
@CrudRepository(entity=User)
class UserRepository:
    async def find_by_email(self, email: str) -> Optional[User]: ...

# Business Logic Layer
@Service()
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def register_user(self, name: str, email: str) -> User:
        # Business logic: validation, creation
        user = User(name=name, email=email)
        return await self.repo.save(user)

# Presentation Layer
@RestController("/api/users")
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @PostMapping("/register")
    async def register(self, body: dict) -> dict:
        user = await self.service.register_user(
            name=body["name"],
            email=body["email"]
        )
        return {"id": user.id, "name": user.name}
```


## In a Nutshell

Mitsuki is opinionated on how applications should be structured. As such, it can make assumptions on structure, which enables many downstream use cases, such as rich metadata for auto-documentation, auto-generating implementations for your domains as defaults (which you can then override if you want them custom), etc.

Many more downstream use cases are currently planned.

The point is - you should be able to focus on the interesting parts - the business logic. Much of the remainder can be automated with sensible defaults, for most apps.

### 1. Convention Over Configuration

Mitsuki uses sensible defaults to minimize boilerplate:
- Components auto-named from class names
- URL paths derived from controller paths
- Database tables mapped from entity class names

### 2. Explicit Over Implicit

Mitsuki favors clarity:
- **Constructor injection only** - Dependencies are visible and testable
- **Type hints required** - Clear contracts between components
- **No magic strings** - Use types and names explicitly

### 3. Decorator-Based Registration

Components register themselves when imported, and express intent:
```python
@Service()
class MyService:
    pass
```

**Automatic Component Scanning:**
Mitsuki automatically scans and imports all Python files in your project directory **recursively** when the application starts. This means:
- All `@Service`, `@Repository`, `@RestController` classes are automatically discovered
- Works across all subdirectories (e.g., `app/controllers/`, `app/services/`, etc.)
- Automatically excludes: `tests/`, `test_*.py`, `migrations/`, `venv/`, `__pycache__/`

No configuration needed for most projects - just organize your code however you like!

### 4. Async-First

All framework operations support async:
- Controllers can be `async def`
- Repository methods are async by default
- Database operations are non-blocking


## Application Lifecycle

**1. Import Phase** - Decorators register components
```python
from mitsuki import Application, Service, RestController

@Service()  # Component registered
class MyService:
    pass
```

**2. Startup Phase** - `Application.run()` called
```python
@Application
class MyApp:
    pass

if __name__ == "__main__":
    MyApp.run()  # Triggers startup
```

**3. Initialization Phase**
- Load configurations - `default` config, `application.yml` config, `application-{profile}.yml` config, env vars. Blends them.
- Process `@Configuration` classes
- Execute `@Provider` factory methods
- Initialize database connections
- Create entity tables

**4. Resolution Phase**
- Resolve all component dependencies
- Create instances in dependency order
- Inject dependencies via constructors

**5. Server Startup**
- Collect all `@RestController` and `@Controller` classes
- Build routing table from `@GetMapping`, `@PostMapping`, etc.
- Start ASGI server

**6. Runtime Phase**
- Handle incoming HTTP requests
- Route to appropriate controller methods
- Execute business logic through services
- Return responses

**7. Shutdown Phase**
- Close database connections
- Clean up resources
- Graceful shutdown

## Configuration

Mitsuki supports multiple configuration sources, with a default config file containing sensible defaults:

**1. application.yml** (primary)
```yaml
server:
  port: 8000

database:
  url: postgresql://localhost/mydb
```

**2. Environment Variables** (override)
```bash
MITSUKI_DATABASE_URL=postgresql://prod/db
MITSUKI_SERVER_PORT=9000
```

**3. Profile-Specific Files**
```yaml
# application-development.yml
# application-production.yml
```

**4. @Value Injection**
```python
@Configuration
class Config:
    port: int = Value("${server.port:8000}")
```

When starting an app, sources are logged:

```
Configuration sources:

[default configuration]
┌──────────────────────────────────────────────────────────────────────┐
│database.adapter              database.echo                           │
│database.pool.enabled         database.pool.max_overflow              │
│database.pool.recycle         database.pool.size                      │
│database.pool.timeout         logging.format                          │
│logging.sqlalchemy            server.cors.allowed_origins             │
│server.max_body_size          server.multipart.max_file_size          │
│server.multipart.max_request_size  server.workers                     │
└──────────────────────────────────────────────────────────────────────┘

[application.yml]
┌──────────────────────────────────────────────────────────────────────┐
│logging.level                 logging.log_config_sources              │
│server.access_log             server.cors.enabled                     │
│server.ignore_trailing_slash  server.type                             │
└──────────────────────────────────────────────────────────────────────┘

[environment variable (MITSUKI_SERVER_PORT)]
┌──────────────────────────────────────────────────────────────────────┐
│server.port                                                            │
└──────────────────────────────────────────────────────────────────────┘
```

## Next Steps

- [Decorators Reference](./02_decorators.md) - Complete guide to all decorators
- [Repositories & Data Layer](./03_repositories.md) - CRUD operations and query DSL
- [Controllers & Routing](./04_controllers.md) - Web request handling
- [Profiles](./05_profiles.md) - Environment-specific configuration
- [Configuration](./06_configuration.md) - Application configuration and providers
- [OpenAPI](./16_openapi.md) - Auto-generated API documentation
