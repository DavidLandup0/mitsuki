# Learning Mitsuki Through a Blog App

This example application demonstrates the key features of the Mitsuki framework by building a simple but complete blog application. It's designed to be a hands-on guide to understanding how Mitsuki's components work together to create a robust and maintainable web application.

## Introduction to Mitsuki

Mitsuki brings powerful features like dependency injection, component auto-scanning, and a declarative approach to web development to the Python ecosystem. This example will walk you through the core concepts of Mitsuki, using the blog app as a practical example.

## Getting Started

### Running the Application

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Run the application:**
    ```bash
    python3 examples/blog_app/app.py
    ```
    The server will start on `http://localhost:8000`.

### Docs

Mitsuki automatically creates OpenAPI-compliant documentation for you, and exposes Swagger, Redocly or Scalar UIs (or all of them), on `/swagger`, `/redoc` and `/scalar` respectively.

The preferred UI chosen by the user (defaults to `scalar`) is also served on `/docs`:

![](docs.png)

### Populating the Database

The application starts with an empty database. To explore the API with some sample data, you can use the `populate` endpoint:

```bash
curl -X POST http://localhost:8000/api/posts/populate
```

This will create a few users and posts so you can start experimenting with the API right away.

## Core Concepts of Mitsuki

This blog application is built around Mitsuki's core concepts. Let's explore them one by one.

### `@Application`: The Heart of Your App

The `@Application` decorator marks the main entry point of your application. It's responsible for configuring and running the app, including setting up the server, database, and other components.

In our blog app, `app.py` contains the `BlogApp` class decorated with `@Application`:

```python
# examples/blog_app/app.py

from mitsuki import Application

@Application
class BlogApp:
    """Blog application configuration."""
    pass

if __name__ == "__main__":
    BlogApp.run()
```

Configuration can be provided via class attributes or `application.yml`. The `@Application` decorator also triggers **component auto-scanning**. Mitsuki will automatically discover and register all components (`@RestController`, `@Service`, `@CrudRepository`, `@Entity`) in the application directory.

### `@RestController`: Building Your API

The `@RestController` decorator is used to define a REST controller, which is a class that handles HTTP requests. Each method in a controller can be mapped to a specific URL and HTTP method using decorators like `@GetMapping`, `@PostMapping`, etc.

Here's a snippet from our `PostController` in `controllers.py`:

```python
# examples/blog_app/controllers.py

@RestController("/api/posts")
class PostController:
    def __init__(self, post_service: PostService, user_service: UserService):
        self.post_service = post_service
        self.user_service = user_service

    @GetMapping("/")
    async def get_posts(
        self, page: int = QueryParam(default=0), size: int = QueryParam(default=20)
    ):
        """Get paginated list of published posts."""
        posts = await self.post_service.search_posts("", page=page, page_size=size)
        return {"posts": [p.to_dto() for p in posts], "page": page, "size": size}
```

### `@Service`: The Business Logic Layer

The `@Service` decorator marks a class as a service, which is where your application's business logic resides. Services are responsible for coordinating data access and implementing the core functionality of your application.

Our `PostService` in `services.py` is a good example:

```python
# examples/blog_app/services.py

@Service()
class PostService:
    def __init__(self, post_repo: PostRepository):
        self.post_repo = post_repo

    async def create_post(
        self, title: str, slug: str, content: str, author_id: int
    ) -> Post:
        """Create a new blog post."""
        post = Post(title=title, slug=slug, content=content, author_id=author_id)
        return await self.post_repo.save(post)
```

### `@CrudRepository`: Effortless Database Operations

The `@CrudRepository` decorator is used to create a repository, which provides a simple and consistent way to interact with your database. By default, it provides methods for creating, reading, updating, and deleting records (`save`, `find_by_id`, `find_all`, `delete_by_id`, etc.).

Our `PostRepository` in `repositories.py`:

```python
# examples/blog_app/repositories.py

@CrudRepository(entity=Post)
class PostRepository:
    """Repository for Post entity with custom queries."""

    # Query DSL methods - automatically implemented
    async def find_by_slug(self, slug: str): ...
    async def find_by_author_id(self, author_id: int): ...
    async def count_by_published(self, published: bool) -> int: ...
```

### `@Entity`: Defining Your Data Models

The `@Entity` decorator is used to define a database model. Mitsuki uses these models to automatically create the database tables when the application starts.

Here's the `Post` entity from `models.py`:

```python
# examples/blog_app/models.py

@Entity()
@dataclass
class Post:
    """Blog post entity."""

    id: int = Id()
    title: str = ""
    slug: str = Column(unique=True)
    content: str = ""
    author_id: int = 0
    views: int = 0
    published: bool = False
    published_at: Optional[datetime] = None
    created_at: datetime = Field(update_on_create=True)
    updated_at: datetime = Field(update_on_save=True)

    def to_dto(self):
        """Convert to PostDTO for API responses."""
        from dtos import PostDTO
        return PostDTO(
            id=self.id,
            title=self.title,
            slug=self.slug,
            content=self.content,
            author_id=self.author_id,
            views=self.views,
            published=self.published,
            published_at=self.published_at.isoformat() if self.published_at else None,
            created_at=self.created_at.isoformat(),
        )
```

### Dependency Injection: Automatic Wiring

Mitsuki's dependency injection mechanism automatically wires your components together. When Mitsuki creates an instance of a component (like a controller or a service), it automatically injects the dependencies declared in its `__init__` method.

For example, in our `PostController`, the `PostService` is automatically injected:

```python
@RestController("/api/posts")
class PostController:
    def __init__(self, post_service: PostService, user_service: UserService):
        self.post_service = post_service  # Injected by Mitsuki!
        self.user_service = user_service  # Injected by Mitsuki!
```

### `@Query` and `@Modifying`: Custom Database Queries

For more complex database operations, you can use the `@Query` and `@Modifying` decorators to define custom queries in your repositories.

#### `@Query` with Named Parameters

```python
# examples/blog_app/repositories.py

@Query("""
    SELECT p FROM Post p
    WHERE (p.title LIKE :search OR p.content LIKE :search)
    AND p.published = :published
    ORDER BY p.published_at DESC
""")
async def search_posts(
    self, search: str, published: bool, limit: int, offset: int
): ...
```

#### `@Query` with Positional Parameters

```python
# examples/blog_app/repositories.py

@Query("""
    SELECT p FROM Post p
    WHERE p.author_id = ?1
    AND p.published = ?2
    ORDER BY p.created_at DESC
""")
async def find_by_author_and_status(
    self, author_id: int, published: bool, limit: int, offset: int
): ...
```

#### `@Modifying` for `UPDATE`/`DELETE`

```python
# examples/blog_app/repositories.py

@Modifying
@Query("UPDATE Post p SET p.views = p.views + 1 WHERE p.id = :id")
async def increment_views(self, id: int) -> int: ...
```

### Custom SQLAlchemy Queries with `get_connection()`

For complex analytics or queries that require SQLAlchemy Core, repositories can use `get_connection()`:

```python
# examples/blog_app/repositories.py

async def get_user_stats(self, min_posts: int = 0):
    """Get user statistics using custom SQLAlchemy Core queries."""
    async with self.get_connection() as conn:
        adapter = get_database_adapter()

        # Get SQLAlchemy Table objects
        user_table = adapter.get_table(User)
        post_table = adapter.get_table(Post)

        # Build query with SQLAlchemy Core
        query = (
            select(
                user_table.c.id,
                user_table.c.username,
                user_table.c.email,
                func.count(post_table.c.id).label("post_count"),
                func.sum(post_table.c.views).label("total_views"),
            )
            .select_from(user_table)
            .outerjoin(post_table, user_table.c.id == post_table.c.author_id)
            .where(user_table.c.active == True)
            .group_by(user_table.c.id, user_table.c.username, user_table.c.email)
            .having(func.count(post_table.c.id) >= min_posts)
            .order_by(func.count(post_table.c.id).desc())
        )

        result = await conn.execute(query)
        rows = result.fetchall()
        return [...]
```

### `@Produces` and `@Consumes`: Request/Response Validation

Mitsuki provides powerful validation decorators for ensuring type safety:

```python
# examples/blog_app/controllers.py

@GetMapping("/{id}")
@Produces(UserDTO)
async def get_user(self, id: int = PathVariable()):
    """Get user by ID with output validation."""
    user = await self.user_service.get_user_by_id(id)
    if not user:
        return ResponseEntity.not_found({"error": "User not found"})
    return user.to_dto()

@PutMapping("/{id}")
@Produces(UserDTO)
@Consumes(UpdateUserRequest)
async def update_user(
    self, id: int = PathVariable(), data: UpdateUserRequest = RequestBody()
):
    """Update user with input and output validation."""
    updated = await self.user_service.update_user(
        user_id=id, username=data.username, email=data.email, bio=data.bio
    )
    if not updated:
        return ResponseEntity.not_found({"error": "User not found"})
    return updated.to_dto()
```

## API Endpoints

Here's a summary of the available API endpoints. After populating the database, you can try them out yourself!

### Posts

#### `POST /api/posts/populate`
Populate the database with sample data.

```bash
curl -X POST http://localhost:8000/api/posts/populate
```

**Response:**
```json
{
    "message": "Database populated with sample data"
}
```

#### `GET /api/posts`
Get all published posts with pagination.

```bash
curl http://localhost:8000/api/posts
```

**Response:**
```json
{
    "posts": [
        {
            "id": 3,
            "title": "Building REST APIs with Mitsuki",
            "slug": "building-rest-apis",
            "content": "In this tutorial, we will build a simple REST API...",
            "author_id": 2,
            "views": 0,
            "published": 1,
            "published_at": "2025-11-19T22:35:11.626701",
            "created_at": "2025-11-19T22:35:11.618130"
        },
        {
            "id": 2,
            "title": "Advanced @Query Decorator Usage",
            "slug": "advanced-query-decorator",
            "content": "The @Query decorator in Mitsuki allows you to write custom queries...",
            "author_id": 1,
            "views": 0,
            "published": 1,
            "published_at": "2025-11-19T22:35:11.624179",
            "created_at": "2025-11-19T22:35:11.615647"
        }
    ],
    "page": 0,
    "size": 20
}
```

#### `GET /api/posts/search`
Search for posts by title or content.

```bash
curl "http://localhost:8000/api/posts/search?q=Query"
```

**Response:**
```json
{
    "posts": [
        {
            "id": 2,
            "title": "Advanced @Query Decorator Usage",
            "slug": "advanced-query-decorator",
            "content": "The @Query decorator in Mitsuki allows you to write custom queries...",
            "author_id": 1,
            "views": 0,
            "published": 1,
            "published_at": "2025-11-19T22:35:11.624179",
            "created_at": "2025-11-19T22:35:11.615647"
        }
    ],
    "query": "Query",
    "page": 0,
    "size": 20
}
```

#### `GET /api/posts/{slug}`
Get a specific post by its slug (increments view count automatically).

```bash
curl http://localhost:8000/api/posts/getting-started-mitsuki
```

**Response:**
```json
{
    "id": 1,
    "title": "Getting Started with Mitsuki Framework",
    "slug": "getting-started-mitsuki",
    "content": "Mitsuki is an opinionated web development framework for Python...",
    "author_id": 1,
    "views": 1,
    "published": true,
    "published_at": "2025-11-19T22:35:11.620544",
    "created_at": "2025-11-19T22:35:11.612309"
}
```

#### `GET /api/posts/author/{author_id}`
Get posts by a specific author.

```bash
curl http://localhost:8000/api/posts/author/1
```

**Response:**
```json
{
    "posts": [
        {
            "id": 2,
            "title": "Advanced @Query Decorator Usage",
            "slug": "advanced-query-decorator",
            "content": "The @Query decorator in Mitsuki allows you to write custom queries...",
            "author_id": 1,
            "views": 0,
            "published": 1,
            "published_at": "2025-11-19T22:35:11.624179",
            "created_at": "2025-11-19T22:35:11.615647"
        },
        {
            "id": 1,
            "title": "Getting Started with Mitsuki Framework",
            "slug": "getting-started-mitsuki",
            "content": "Mitsuki is an opinionated web development framework for Python...",
            "author_id": 1,
            "views": 1,
            "published": 1,
            "published_at": "2025-11-19T22:35:11.620544",
            "created_at": "2025-11-19T22:35:11.612309"
        }
    ],
    "author_id": 1,
    "page": 0,
    "size": 20
}
```

#### `POST /api/posts/`
Create a new post.

```bash
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title": "New Post", "slug": "new-post", "content": "This is a new post", "author_id": 3}'
```

**Response:**
```json
{
    "id": 4,
    "title": "New Post",
    "slug": "new-post",
    "content": "This is a new post",
    "author_id": 3,
    "views": 0,
    "published": false,
    "published_at": null,
    "created_at": "2025-11-19T22:36:15.452253"
}
```

#### `PUT /api/posts/{id}/publish`
Publish a post.

```bash
curl -X PUT http://localhost:8000/api/posts/4/publish
```

**Response:**
```json
{
    "message": "Post published successfully"
}
```

#### `POST /api/posts/{id}/upload-image`
Upload an image for a post (demonstrates file upload with validation).

```bash
curl -X POST http://localhost:8000/api/posts/1/upload-image \
  -F "image=@/path/to/image.jpg" \
  -F "alt_text=Post image"
```

**Response:**
```json
{
    "message": "Image uploaded successfully",
    "post_id": 1,
    "filename": "image.jpg",
    "size": 11234,
    "content_type": "image/jpeg",
    "alt_text": "Post image",
    "url": "/uploads/posts/1_image.jpg"
}
```

#### `GET /api/posts/analytics`
Get post analytics using custom SQLAlchemy query.

```bash
curl http://localhost:8000/api/posts/analytics
```

**Response:**
```json
{
    "total_posts": 3,
    "published_posts": 3,
    "total_views": 1,
    "avg_views": 0.33
}
```

### Users

#### `GET /api/users`
Get all active users with pagination (demonstrates `@Produces` validation).

```bash
curl http://localhost:8000/api/users
```

**Response:**
```json
[
    {
        "id": 2,
        "username": "bob",
        "email": "bob@example.com",
        "bio": "",
        "active": 1,
        "created_at": "2025-11-19T22:35:11.608821"
    },
    {
        "id": 1,
        "username": "alice",
        "email": "alice@example.com",
        "bio": "",
        "active": 1,
        "created_at": "2025-11-19T22:35:11.604222"
    }
]
```

#### `GET /api/users/{id}`
Get a specific user by ID.

```bash
curl http://localhost:8000/api/users/1
```

**Response:**
```json
{
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "bio": "",
    "active": true,
    "created_at": "2025-11-19T22:35:11.604222"
}
```

#### `POST /api/users/`
Create a new user (demonstrates `@Consumes` and `@Produces`).

```bash
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"username": "charlie", "email": "charlie@example.com", "password": "pass123", "bio": "New user"}'
```

**Response:**
```json
{
    "id": 3,
    "username": "charlie",
    "email": "charlie@example.com",
    "bio": "New user",
    "active": true,
    "created_at": "2025-11-19T22:35:59.663072"
}
```

#### `PUT /api/users/{id}`
Update user information (demonstrates `@Consumes(UpdateUserRequest)`).

```bash
curl -X PUT http://localhost:8000/api/users/1 \
  -H "Content-Type: application/json" \
  -d '{"bio": "Updated bio for Alice"}'
```

**Response:**
```json
{
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "bio": "Updated bio for Alice",
    "active": true,
    "created_at": "2025-11-19T22:35:11.604222"
}
```

#### `GET /api/users/public`
Get users with email field excluded (demonstrates `exclude_fields`).

```bash
curl http://localhost:8000/api/users/public
```

**Response:**
```json
[
    {
        "id": 3,
        "username": "charlie",
        "bio": "New user",
        "active": 1,
        "created_at": "2025-11-19T22:35:59.663072"
    },
    {
        "id": 2,
        "username": "bob",
        "bio": "",
        "active": 1,
        "created_at": "2025-11-19T22:35:11.608821"
    }
]
```

Note: The `email` field is excluded from the response.

#### `GET /api/users/stats`
Get user statistics with custom SQLAlchemy analytics query.

```bash
curl http://localhost:8000/api/users/stats
```

**Response:**
```json
[
    {
        "id": 1,
        "username": "alice",
        "email": "alice@example.com",
        "post_count": 2,
        "total_views": 1
    },
    {
        "id": 2,
        "username": "bob",
        "email": "bob@example.com",
        "post_count": 1,
        "total_views": 0
    }
]
```

## What This Example Demonstrates

This blog app showcases:

- **Dependency Injection** - Automatic component wiring
- **RESTful Controllers** - `@RestController`, `@GetMapping`, `@PostMapping`, `@PutMapping`
- **Services** - Business logic layer with `@Service`
- **Repositories** - Database access with `@CrudRepository`
- **Entities** - Data models with `@Entity`
- **Query DSL** - Automatic query generation (`find_by_X`, `count_by_X`)
- **Custom Queries** - `@Query` with named and positional parameters
- **Modifying Queries** - `@Modifying` for UPDATE/DELETE operations
- **SQLAlchemy Integration** - Custom analytics with `get_connection()`
- **Request/Response Validation** - `@Produces` and `@Consumes` decorators
- **Field Exclusion** - Hide sensitive fields with `exclude_fields`
- **File Uploads** - Handle multipart form data with validation
- **Pagination** - Query parameters for paging results
- **OpenAPI Generation** - Automatic API documentation

We hope this example helps you get started with the Mitsuki framework. Happy coding!
