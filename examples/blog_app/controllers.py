import hashlib
import os

from dtos import CreateUserRequest, UpdateUserRequest, UserDTO
from services import PostService, UserService

from mitsuki import (
    Consumes,
    FormFile,
    FormParam,
    GetMapping,
    PathVariable,
    PostMapping,
    Produces,
    PutMapping,
    QueryParam,
    RequestBody,
    ResponseEntity,
    RestController,
    UploadFile,
)


@RestController("/api/users")
class UserController:
    """REST API for users - demonstrates @Produces and @Consumes."""

    def __init__(self, user_service: UserService):
        self.user_service = user_service

    @GetMapping("/")
    @Produces(UserDTO)
    async def get_users(
        self, page: int = QueryParam(default=0), size: int = QueryParam(default=20)
    ):
        """Get all active users. Uses @Produces decorator for output validation."""
        users = await self.user_service.get_active_users(page=page, page_size=size)
        return [u.to_dto() for u in users]

    @GetMapping("/{id}")
    @Produces(UserDTO)
    async def get_user(self, id: int = PathVariable()):
        """Get user by ID with output validation."""
        user = await self.user_service.get_user_by_id(id)
        if not user:
            return ResponseEntity.not_found({"error": "User not found"})
        return user.to_dto()

    @PostMapping("/")
    @Produces(UserDTO)
    @Consumes(CreateUserRequest)
    async def create_user(self, data: CreateUserRequest = RequestBody()):
        """
        Create a new user.
        Uses @Consumes to validate input and @Produces for output.
        The data parameter will be a CreateUserRequest dataclass instance.
        """
        password_hash = hashlib.sha256(data.password.encode()).hexdigest()

        user = await self.user_service.create_user(
            username=data.username, email=data.email, password_hash=password_hash
        )

        user.bio = data.bio
        await self.user_service.user_repo.save(user)

        return ResponseEntity.created(user.to_dto())

    @PutMapping("/{id}")
    @Produces(UserDTO)
    @Consumes(UpdateUserRequest)
    async def update_user(
        self, id: int = PathVariable(), data: UpdateUserRequest = RequestBody()
    ):
        """
        Update user information.
        Input validated against UpdateUserRequest, output against UserDTO.
        """
        updated = await self.user_service.update_user(
            user_id=id, username=data.username, email=data.email, bio=data.bio
        )

        if not updated:
            return ResponseEntity.not_found({"error": "User not found"})

        return updated.to_dto()

    @GetMapping("/public", exclude_fields=["email"])
    @Produces(UserDTO)
    async def get_public_users(
        self, page: int = QueryParam(default=0), size: int = QueryParam(default=20)
    ):
        """
        Get users with email field hidden.
        Combines @Produces validation with exclude_fields filtering.
        """
        users = await self.user_service.get_active_users(page=page, page_size=size)
        return [u.to_dto() for u in users]

    @GetMapping("/stats")
    async def get_user_stats(self, min_posts: int = QueryParam(default=0)):
        """
        Get user statistics using custom SQLAlchemy query.
        Demonstrates get_connection() usage for complex queries.
        """
        return await self.user_service.get_user_stats(min_posts=min_posts)


@RestController("/api/posts")
class PostController:
    """REST API for blog posts."""

    def __init__(self, post_service: PostService, user_service: UserService):
        self.post_service = post_service
        self.user_service = user_service

    @PostMapping("/populate")
    async def populate_data(self):
        """Populate the database with sample data."""
        user1 = await self.user_service.create_user(
            "alice", "alice@example.com", hashlib.sha256(b"password1").hexdigest()
        )
        user2 = await self.user_service.create_user(
            "bob", "bob@example.com", hashlib.sha256(b"password2").hexdigest()
        )

        post1 = await self.post_service.create_post(
            title="Getting Started with Mitsuki Framework",
            slug="getting-started-mitsuki",
            content="Mitsuki is an opinionated web development framework for Python...",
            author_id=user1.id,
        )
        post2 = await self.post_service.create_post(
            title="Advanced @Query Decorator Usage",
            slug="advanced-query-decorator",
            content="The @Query decorator in Mitsuki allows you to write custom queries...",
            author_id=user1.id,
        )
        post3 = await self.post_service.create_post(
            title="Building REST APIs with Mitsuki",
            slug="building-rest-apis",
            content="In this tutorial, we will build a simple REST API...",
            author_id=user2.id,
        )

        await self.post_service.publish_post(post1.id)
        await self.post_service.publish_post(post2.id)
        await self.post_service.publish_post(post3.id)

        return {"message": "Database populated with sample data"}

    @GetMapping("/")
    async def get_posts(
        self, page: int = QueryParam(default=0), size: int = QueryParam(default=20)
    ):
        """Get paginated list of published posts."""
        posts = await self.post_service.search_posts("", page=page, page_size=size)
        return {"posts": [p.to_dto() for p in posts], "page": page, "size": size}

    @GetMapping("/public", exclude_fields=["author_id"])
    async def get_public_posts(
        self, page: int = QueryParam(default=0), size: int = QueryParam(default=20)
    ):
        """Get posts with sensitive fields removed."""
        posts = await self.post_service.search_posts("", page=page, page_size=size)
        return {"posts": [p.to_dto() for p in posts], "page": page, "size": size}

    @GetMapping("/search")
    async def search_posts(
        self,
        q: str = QueryParam(default=""),
        page: int = QueryParam(default=0),
        size: int = QueryParam(default=20),
    ):
        """Search posts by title/content."""
        posts = await self.post_service.search_posts(query=q, page=page, page_size=size)
        return {
            "posts": [p.to_dto() for p in posts],
            "query": q,
            "page": page,
            "size": size,
        }

    @GetMapping("/{slug}")
    async def get_post(self, slug: str = PathVariable()):
        """Get post by slug (increments view count)."""
        post = await self.post_service.get_post_by_slug(slug)
        if not post:
            return ResponseEntity.not_found({"error": "Post not found"})
        return post.to_dto()

    @PostMapping("/")
    async def create_post(self, data: dict = RequestBody()):
        """Create a new post."""
        post = await self.post_service.create_post(
            title=data["title"],
            slug=data["slug"],
            content=data["content"],
            author_id=data["author_id"],
        )
        return ResponseEntity.created(post.to_dto())

    @PostMapping("/{id}/upload-image")
    async def upload_post_image(
        self,
        id: int = PathVariable(),
        image: UploadFile = FormFile(
            allowed_types=["image/jpeg", "image/png", "image/gif", "image/webp"],
            max_size=5 * 1024 * 1024,  # 5MB
        ),
        alt_text: str = FormParam(default=""),
    ):
        """
        Upload an image for a blog post.
        Demonstrates file upload with validation and form parameters.
        """
        upload_dir = "uploads/posts"
        os.makedirs(upload_dir, exist_ok=True)

        filename = f"{id}_{image.filename}"
        filepath = os.path.join(upload_dir, filename)

        await image.save(filepath)

        return {
            "message": "Image uploaded successfully",
            "post_id": id,
            "filename": image.filename,
            "size": image.size,
            "content_type": image.content_type,
            "alt_text": alt_text,
            "url": f"/uploads/posts/{filename}",
        }

    @PutMapping("/{id}/publish")
    async def publish_post(self, id: int = PathVariable()):
        """Publish a post."""
        success = await self.post_service.publish_post(id)
        if not success:
            return ResponseEntity.not_found({"error": "Post not found"})
        return {"message": "Post published successfully"}

    @GetMapping("/author/{author_id}")
    async def get_author_posts(
        self,
        author_id: int = PathVariable(),
        published: bool = QueryParam(default=True),
        page: int = QueryParam(default=0),
        size: int = QueryParam(default=20),
    ):
        """Get posts by author."""
        posts = await self.post_service.get_author_posts(
            author_id=author_id, published=published, page=page, page_size=size
        )
        return {
            "posts": [p.to_dto() for p in posts],
            "author_id": author_id,
            "page": page,
            "size": size,
        }

    @GetMapping("/analytics")
    async def get_post_analytics(self):
        """
        Get post analytics using custom SQLAlchemy query.
        Demonstrates get_connection() for analytics.
        """
        return await self.post_service.get_post_analytics()
