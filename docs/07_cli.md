# Mitsuki CLI

The Mitsuki CLI provides tools for bootstrapping new Mitsuki applications with a complete project structure.

## Installation

The CLI is automatically available when you install Mitsuki:

```bash
pip install mitsuki
```

## Commands

### mitsuki init

Create a new Mitsuki application with an interactive wizard.

```bash
mitsuki init
```

The command will prompt you for:

1. **Application name** - The name of your application (converted to snake_case)
2. **Description** - Optional description for your application
3. **Database type** - Choose between:
   - SQLite (default, good for development)
   - PostgreSQL (recommended for production)
   - MySQL
4. **Create starter domain?** - Whether to generate an example domain object
5. **Domain name** - If creating a domain, specify the name (e.g., User, Product, Post)
6. **Add another domain?** - Create multiple domains in one go

## Project Structure

The CLI generates the following structure:

```
my_app/
  src/
    my_app/
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

## Example Usage

### Basic Application (No Domain)

```bash
$ mitsuki init
Application name: blog_api
Description (optional): My blog API
Database type [sqlite/postgresql/mysql] (sqlite):
Create starter domain? [Y/n]: n

Successfully created Mitsuki application: blog_api

To get started:
  cd blog_api
  pip install mitsuki
  MITSUKI_PROFILE=development python src/app.py
```

### Application with Domain

```bash
$ mitsuki init
Application name: blog_api
Description (optional): My blog API
Database type [sqlite/postgresql/mysql] (sqlite): postgresql
Create starter domain? [Y/n]: y
Domain name (e.g., User, Product): Post
Add another domain? [y/N]: y
Domain name: Comment
Add another domain? [y/N]: n

Successfully created Mitsuki application: blog_api
```

This generates a complete CRUD application with:

**Post Entity** (`src/blog_api/domain/post.py`):

```python
import uuid
from dataclasses import dataclass
from datetime import datetime
from mitsuki import Entity, UUIDv7, Field

@Entity()
@dataclass
class Post:
    id: uuid.UUID = UUIDv7()
    created_at: datetime = Field(update_on_create=True)
    updated_at: datetime = Field(update_on_save=True)
```

**Post Repository** (`src/blog_api/repository/post_repository.py`):

```python
from mitsuki import CrudRepository
from ..domain.post import Post

@CrudRepository(entity=Post)
class PostRepository:
    """Repository for Post entities, with auto-implemented CRUD methods."""
    pass
```

**Post Service** (`src/blog_api/service/post_service.py`):

```python
import uuid
from typing import List, Optional
from mitsuki import Service
from ..domain.post import Post
from ..repository.post_repository import PostRepository

@Service()
class PostService:
    """Service layer for Post business logic."""

    def __init__(self, repo: PostRepository):
        self.repo = repo

    async def get_by_id(self, id: uuid.UUID) -> Optional[Post]:
        """Get post by ID"""
        return await self.repo.find_by_id(id)

    async def get_all(self) -> List[Post]:
        """Get all posts"""
        return await self.repo.find_all()

    async def create(self, post: Post) -> Post:
        """Create new post"""
        return await self.repo.save(post)

    async def update(self, post: Post) -> Post:
        """Update existing post"""
        return await self.repo.save(post)

    async def delete(self, id: uuid.UUID) -> bool:
        """Delete post by ID"""
        return await self.repo.delete_by_id(id)
```

**Post Controller** (`src/blog_api/controller/post_controller.py`):

```python
import uuid
from typing import List
from mitsuki import RestController, GetMapping, PostMapping, PutMapping, DeleteMapping, RequestBody, PathVariable
from ..domain.post import Post
from ..service.post_service import PostService

@RestController(path="/api/post")
class PostController:
    """REST controller for Post operations."""

    def __init__(self, service: PostService):
        self.service = service

    @GetMapping()
    async def list_all(self) -> List[Post]:
        """Get all posts"""
        return await self.service.get_all()

    @GetMapping("/{id}")
    async def get_by_id(self, id: str = PathVariable()) -> Post:
        """Get post by ID"""
        entity = await self.service.get_by_id(uuid.UUID(id))
        if not entity:
            raise ValueError(f"Post not found: {id}")
        return entity

    @PostMapping()
    async def create(self, post: Post = RequestBody()) -> Post:
        """Create new post"""
        return await self.service.create(post)

    @PutMapping("/{id}")
    async def update(self, id: str = PathVariable(), post: Post = RequestBody()) -> Post:
        """Update post"""
        post.id = uuid.UUID(id)
        return await self.service.update(post)

    @DeleteMapping("/{id}")
    async def delete(self, id: str = PathVariable()) -> dict:
        """Delete post"""
        success = await self.service.delete(uuid.UUID(id))
        return {"deleted": success}
```

## Generated Configuration

The CLI generates environment-specific configuration files:

**application.yml** (base configuration):

```yaml
server:
  host: 0.0.0.0
  port: 8000

database:
  url: sqlite:///blog_api.db  # or postgresql://localhost/blog_api
  echo: true
```

**application-dev.yml** (development overrides):

```yaml
database:
  url: sqlite:///blog_api.db
  echo: true
  pool:
    enabled: false

logging:
  level: DEBUG
  sqlalchemy: true

app:
  debug: true
```

**application-prod.yml** (production overrides):

```yaml
database:
  url: postgresql://localhost/blog_api_production
  echo: false
  pool:
    enabled: true
    size: 50
    max_overflow: 100

logging:
  level: WARNING
  sqlalchemy: false

app:
  debug: false
```

## Running Your Application

After creating your application:

```bash
cd my_app

# Development mode
MITSUKI_PROFILE=development python src/app.py

# Staging mode
MITSUKI_PROFILE=staging python src/app.py

# Production mode
MITSUKI_PROFILE=production python src/app.py
```

The server will start on http://127.0.0.1:8000 by default.

## API Endpoints

For each generated domain, the CLI creates the following REST endpoints:

- `GET /api/{domain}` - List all entities
- `GET /api/{domain}/{id}` - Get entity by ID (UUID)
- `POST /api/{domain}` - Create new entity
- `PUT /api/{domain}/{id}` - Update entity
- `DELETE /api/{domain}/{id}` - Delete entity

## Default Entity Fields

All generated entities include:

- `id: uuid.UUID` - Primary key using UUID v7 (time-ordered UUIDs)
- `created_at: datetime` - Automatically set on creation
- `updated_at: datetime` - Automatically updated on save

You can add additional fields to your entities as needed.

## Database Support

The CLI configures your application for the selected database:

- **SQLite**
- **PostgreSQL**
- **MySQL**

## Next Steps

After generating your application:

1. **Add fields to your entities** - Edit the `domain/*.py` files
2. **Implement business logic** - Add methods to your service classes
3. **Add custom endpoints** - Create new controller methods with `@GetMapping`, `@PostMapping`, etc.
4. **Configure database connection** - Update `application-{env}.yml` with your database credentials
5. **Add and run migrations** - Mitsuki automatically creates tables on startup for convinience, but choose a tool per your taste for handling an evolving database schema.

## See Also

- [Entities and Repositories](03_repositories.md)
- [Controllers](04_controllers.md)
- [Configuration](06_configuration.md)
- [Profiles](05_profiles.md)
