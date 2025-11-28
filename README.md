```
                                       ♡ ｡ ₊°༺❤︎༻°₊ ｡ ♡
                                          _ __             __   _
                               ____ ___  (_) /________  __/ /__(_)
                              / __ `__ \/ / __/ ___/ / / / //_/ /
                             / / / / / / / /_(__  ) /_/ / ,< / /
                            /_/ /_/ /_/_/\__/____/\__,_/_/|_/_/
                                    °❀˖ ° °❀⋆.ೃ࿔*:･  ° ❀˖°

```

<div align="center">
<p><i>Come with me, take the journey. ❀</i></p>
</div>

<hr>

<div align="center">
<p><strong>Enterprise patterns of Spring Boot, development speed and flexibility of Python. </strong></p>
<p><strong>No compromises.</strong></p>
</div>

<div align="center">
<a href="/docs">Documentation</a> |
<a href="/benchmarks">Benchmarks</a> |
<a href="https://deepwiki.com/DavidLandup0/mitsuki">DeepWiki</a>
</div>
<hr>


## Quickstart

```bash
pip install mitsuki
```

Create `app.py`:

```python
from mitsuki import Application, RestController, GetMapping

@RestController("/") # Or @Router or @Controller
class HelloController:
    @Get("/hello/{name}") # Or @GetMapping
    async def hello(self, name: str) -> dict:
        return {"message": f"Hello, {name}!"}

@Application
class App:
    pass

if __name__ == "__main__":
    App.run()
```

Run it:

```bash
python app.py
```

Hit it:

```bash
curl http://localhost:8000/hello/world
# {"message": "Hello, world!"}
```

### OpenAPI Generation

Mitsuki automatically generates an OpenAPI 3.0 specification for your API, and supports Swagger, Redocly and Scalar UIs.

All can run in parallel, and a preferred UI gets exposed at /docs:

- **Swagger UI:** `http://localhost:8000/swagger`
- **ReDoc:** `http://localhost:8000/redoc`
- **Scalar:** `http://localhost:8000/scalar`
- **Preferred:** `http://localhost:8000/docs` # Any one of the three above
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

![](examples/blog_app/docs.png)

No configuration needed.

## CLI Tool

Bootstrap new projects with the `mitsuki` CLI.

```bash
mitsuki init
```

This will guide you through creating a new project with a clean structure and will auto-generate controllers, services, repositories, and configuration for different environments:

```
my_app/
  src/
    domain/           # @Entity classes
    repository/       # @CrudRepository classes
    service/          # @Service classes
    controller/       # @RestController classes
    __init__.py
    app.py             # Application entry point
application.yml      # Base configuration
application-dev.yml  # Development configuration
application-stg.yml  # Staging configuration
application-prod.yml # Production configuration
.gitignore
README.md
```

Start it:

```
python src/app.py 
```

```
2025-11-20 02:04:45,960 - mitsuki - INFO     - 
2025-11-20 02:04:45,960 - mitsuki - INFO     -     ♡ ｡ ₊°༺❤︎༻°₊ ｡ ♡
2025-11-20 02:04:45,960 - mitsuki - INFO     -               _ __             __   _
2025-11-20 02:04:45,960 - mitsuki - INFO     -    ____ ___  (_) /________  __/ /__(_)
2025-11-20 02:04:45,960 - mitsuki - INFO     -   / __ `__ \/ / __/ ___/ / / / //_/ /
2025-11-20 02:04:45,960 - mitsuki - INFO     -  / / / / / / / /_(__  ) /_/ / ,< / /
2025-11-20 02:04:45,960 - mitsuki - INFO     - /_/ /_/ /_/_/\__/____/\__,_/_/|_/_/
2025-11-20 02:04:45,960 - mitsuki - INFO     -     °❀˖ ° °❀⋆.ೃ࿔*:･  ° ❀˖°
2025-11-20 02:04:45,960 - mitsuki - INFO     - 
2025-11-20 02:04:45,960 - mitsuki - INFO     - :: Mitsuki ::                (0.1.2)
2025-11-20 02:04:45,960 - mitsuki - INFO     - 
2025-11-20 02:04:45,960 - mitsuki - INFO     - Mitsuki application starting on http://127.0.0.1:8000
2025-11-20 02:04:45,961 - _granian - INFO     - Starting granian (main PID: 19002)
2025-11-20 02:04:45,967 - _granian - INFO     - Listening at: http://127.0.0.1:8000
2025-11-20 02:04:45,976 - _granian - INFO     - Spawning worker-1 with PID: 19005
2025-11-20 02:04:46,370 - _granian.workers - INFO     - Started worker-1
2025-11-20 02:04:46,370 - _granian.workers - INFO     - Started worker-1 runtime-1
```

And hit the docs on `http://127.0.0.1:8000/docs`:

![](./docs/public/doc_assets/mitsuki_init.png)

## Bootstrapping Projects in a Minute - from Zero to Functional Starter

Okay, let's go beyond "Hello World" - how long does it take to go from zero to something more functional? Something with a database connection, a domain object, a repository with CRUD capabilities, service and controller?

About a single minute.

Here's a live example, of starting a Mitsuki project, which includes:

- Project setup
- Domain object
- Entity controller, service and repository with functional CRUD

![](./docs/public/doc_assets/mitsuki_starter.gif)


## Why Mitsuki?

Mitsuki brings enterprise strength without enterprise complexity.

This is achieved through bringing dependency injection, declarative controllers, and auto-repositories to Python without the ceremony. It's highly inspired by Spring Boot in its early stages.

### High-Performance and Lightweight

Mitsuki is lightweight, and internally uses Granian for low-level server and Starlette for ASGI. As such - it's as fast as Starlette on Granian. Performance-wise - it ranks in the same category as as Spring Boot (Java) and Express (Node/JavaScript), and higher than FastAPI (Python), Flask (Python) or Django (Python).

![](./benchmarks/results/benchmark_results.png)

For more, read the README.md in `/benchmarks`.

### Productivity

Convention over configuration allows you to focus on business code, not glue. Mitsuki provides sensible default conventions, while allowing you to customize any level whenever you'd like.

### Enterprise Patterns at Low Cognitive Cost

Services tend to evolve into certain time-tested patterns. Mitsuki supports them architecturally. Just write code - and it all fits into place.

### Server-Agnostic

Mitsuki isn't tied to a single server library. We currently support `uvicorn` and `granian`, with experimental support for `socketify`. We use `starlette` as an intermediary ASGI-compliant layer.

```
          ┌──────────────────────────┐
          │    Mitsuki Application   │
          └────────────┬─────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │     Starlette ASGI     │
          │       Framework        │
          └────────────┬───────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
     ┌─────────┐  ┌─────────┐  ┌───────────┐
     │ Granian │  │ Uvicorn │  │ Socketify │
     └─────────┘  └─────────┘  └───────────┘
```

In the future - we will likely not commit to only following the ASGI specification, with plans to support RSGI and likely a custom framework to directly leverage `granian`, `uvicorn` and `socketify` other than through the ASGI interface.

We want to maintain the key components in a plug-and-play fashion, staying up to date with the landscape of tooling. This means not locking the framework into a single paradigm.

## Core Design Principles

- Declarative over imperative. Express intent, not implementation.
- Enterprise patterns, no ceremony.
- Type hints are contracts.
- Fast by design, minimal overhead.

## Core Concepts

Mituski architecturally encourages a logical separation of code into three main categories:

- Controllers (representation layer)
- Services (business layer)
- Repositories (data layer)

And uses those assumptions to enhance developer experience, reducing boilerplate, and provides reasonable defaults for most implementation.

To maximize this - you only need to understand a few core concepts.

### Dependency Injection

Formally, Mitsuki performs Inversion of Control (IoC), which is achieved through Dependency Injection (DI). It does this automatically, so you don't have to resolve dependencies yourself.

In other words - you define dependencies semantically, and Mitsuki handles how they're created, injected, and resolved. 

In yet other words - you define *a thing*, and a `@Provider` puts it into a global container that enables you to use *the thing* in any part of your application, without having to instantiate it or injecting it manually:

```python
@Service()
class EmailService:
    async def send(self, to: str, message: str):
        print(f"Sending to {to}: {message}")

@Service()
class UserService:
    def __init__(self, email_service: EmailService):
        # Mitsuki sees EmailService in __init__, wires it automatically
        self.email = email_service

    async def notify_user(self, email: str):
        await self.email.send(email, "You've got mail!")
```

Type hints are enough. Mitsuki handles the rest.

^ This also makes it super simple to define *configurations* for how you want objects to be built, and simply put them into the mix for them to be used. Want to change Mitsuki's formatter? Inject it into the container and it'll override the formatter in it. Want to change Mitsuki's serializer? Inject it into the container and it'll override the serializer in it.

Mitsuki then distributes your objects across the entire codebase.

### Auto-Repositories - Write Interfaces, Get Implementations

Repositories (data layer) support three levels of methods. CRUD with pagination is auto-supported, just by defining a type:

```python
@Entity()
@dataclass
class Post:
    id: int = Id()
    title: str = ""
    author: str = ""
    views: int = 0

@CrudRepository(entity=Post)
class PostRepository:
    # Built-in methods (auto-implemented):
    # - find_by_id(id) -> Post | None
    # - find_all(page=0, size=10) -> List[Post]
    # - save(entity: Post) -> Post
    # - delete(entity: Post) -> None
    # - count() -> int
    # - exists_by_id(id) -> bool
```

But it also allows you to simply define method names, and auto-generates SQL for you:

```python
@CrudRepository(entity=Post)
class PostRepository:
    # Mitsuki turns these into SQL queries
    async def find_by_email(self, email: str): ...
    async def find_by_username(self, username: str): ...
```

Or write queries yourself:

```python
@CrudRepository(entity=Post)
class PostRepository:

    @Query("""
            SELECT u FROM User u
            WHERE u.active = :active
            ORDER BY u.created_at DESC
        """)
    async def find_active_users(self, active: bool, limit: int, offset: int): ...
```

Or just write your own ORM-backed implementations:

```python
from mitsuki import CrudRepository, Entity, Id, Column
from dataclasses import dataclass

@Entity()
@dataclass
class Post:
    id: int = Id()
    title: str = ""
    author: str = ""
    views: int = 0

@CrudRepository(entity=Post)
class PostRepository:
    # Or write custom SQLAlchemy
    async def find_popular_posts(self):
        async with self.get_connection() as conn:
            query = select(Post).where(Post.views > 1000)
            result = await conn.execute(query)
            return [dict(row._mapping) for row in result.fetchall()]
```

**Query DSL Parsing** - Method names become queries:
- `find_by_email(email)` → `SELECT * WHERE email = ?`
- `find_by_age_greater_than(age)` → `SELECT * WHERE age > ?`
- `count_by_status(status)` → `SELECT COUNT(*) WHERE status = ?`

### Scheduled Tasks

Run background jobs with the `@Scheduled` decorator.

```python
from mitsuki import Service, Scheduled

@Service()
class ReportService:
    @Scheduled(cron="0 0 * * *") # Every hour
    async def generate_hourly_report(self):
        print("Generating hourly report...")

    @Scheduled(fixed_rate=60000) # Every minute
    async def check_system_health(self):
        print("Checking system health...")
```

Or use syntactic sugar:

```python
from mitsuki import Service, Scheduled

@Service()
class ReportService:
    @Scheduled(cron="@daily")  # Equivalent to "0 0 0 * * *"
    async def check_system_health(self):
        print("Checking system health...")
```

### File Uploads

Handle `multipart/form-data` file uploads easily.

```python
from mitsuki import RestController, PostMapping, FormFile, UploadFile

@RestController("/api/uploads")
class UploadController:
    @PostMapping("/")
    async def upload_file(self, file: UploadFile = FormFile()):
        await file.save(f"uploads/{file.filename}")
        return {"filename": file.filename, "size": file.size}
```

### Profiles - One Codebase, All Environments

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

Run in dev:

```bash
MITSUKI_PROFILE=development python app.py
```

Run in production:

```bash
MITSUKI_PROFILE=production python app.py
```

Same code, different environments. Keeps everything across environments explicit and readable.

## Configuration

Create `application.yml` (optional):

```yaml
server:
  port: 8000
  host: 0.0.0.0

database:
  url: sqlite:///app.db

logging:
  level: INFO
```


Inject config into code:
```python
from mitsuki import Configuration, Value

@Configuration
class AppConfig:
    port: int = Value("${server.port:8000}")
    db_url: str = Value("${database.url}")
```

Supports `application-profile.yml`, enabling you to centrally define configurations for different environments easily.

## Documentation

| Guide | What's Inside |
|-------|---------------|
| [Overview](docs/01_overview.md) | Architecture, DI, how everything fits together |
| [Decorators Reference](docs/02_decorators.md) | Complete decorator guide (@Service, @RestController, etc.) |
| [Repositories & Entities](docs/03_repositories.md) | Data layer, auto-repositories, query DSL |
| [Controllers](docs/04_controllers.md) | REST endpoints, request mapping, parameters |
| [Profiles](docs/05_profiles.md) | Environment-specific configuration |
| [Configuration](docs/06_configuration.md) | application.yml, @Value, environment vars |
| [CLI](docs/07_cli.md) | Command-line interface for project scaffolding |
| [Database Queries](docs/08_database_queries.md) | Custom queries, SQLAlchemy integration |
| [Response Entities](docs/09_response_entity.md) | HTTP responses, status codes, headers |
| [Validation](docs/10_request_response_validation.md) | Request/response validation |
| [JSON Serialization](docs/11_json_serialization.md) | Automatic serialization of complex types |
| [Logging](docs/12_logging.md) | Configuring and using logging |
| [File Uploads](docs/13_file_uploads.md) | Handling multipart file uploads |
| [Scheduled Tasks](docs/14_scheduled_tasks.md) | Background jobs with @Scheduled |
| [Metrics](docs/15_metrics.md) | Application monitoring and metrics |
| [OpenAPI](docs/16_openapi.md) | Auto-generated API documentation with Swagger/ReDoc/Scalar |

## Basic Example

A basic example with a domain object, CRUD repository and REST controller/router:

```python
from mitsuki import Application, RestController, Service, CrudRepository, Entity, GetMapping, Id, Column
from dataclasses import dataclass

@Entity()
@dataclass
class User:
    id: int = Id()
    name: str = ""
    email: str = Column(unique=True, default="")

@CrudRepository(entity=User)
class UserRepository:
    pass  # find_by_id, find_all, save, delete - all auto-implemented

@Service()
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get_user(self, user_id: int) -> User:
        return await self.repo.find_by_id(user_id)

@RestController("/api/users")
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @GetMapping("/{id}")
    async def get(self, id: str) -> dict:
        user = await self.service.get_user(int(id))
        return {"id": user.id, "name": user.name, "email": user.email}

@Application
class MyApp:
    pass

if __name__ == "__main__":
    MyApp.run()
```

**What just happened?**
- `UserRepository` got `find_by_id()`, `find_all()`, `save()`, `delete()` for free
- Dependencies wired automatically (no factories, no setup)
- Database created on startup (SQLite by default)
- JSON API running on port 8000

## Contributing

Found a bug? Have an idea? PRs welcome.

1. Fork it
2. Create your feature branch
3. Write tests
4. Submit a PR


Built with ❀ for developers who want enterprise patterns without enterprise pain.