import hashlib
from datetime import datetime

from dtos import CreateUserRequest, UpdateUserRequest, UserDTO
from models import Comment, Post, User
from services import CommentService, PostService, TagService, UserService

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
        # Return User entities - will be validated against UserDTO
        return [self._user_to_dto(u) for u in users]

    @GetMapping("/{id}")
    @Produces(UserDTO)
    async def get_user(self, id: int = PathVariable()):
        """Get user by ID with output validation."""
        # For demo purposes, creating a mock user
        # In real app, would fetch from database
        return ResponseEntity.ok(
            UserDTO(
                id=id,
                username=f"user{id}",
                email=f"user{id}@example.com",
                bio="Sample bio",
                active=True,
                created_at=datetime.now().isoformat(),
            )
        )

    @PostMapping("/")
    @Produces(UserDTO)
    @Consumes(CreateUserRequest)
    async def create_user(self, data: CreateUserRequest = RequestBody()):
        """
        Create a new user.
        Uses @Consumes to validate input and @Produces for output.
        The data parameter will be a CreateUserRequest dataclass instance.
        """
        # Hash password
        password_hash = hashlib.sha256(data.password.encode()).hexdigest()

        # Create user
        user = await self.user_service.create_user(
            username=data.username, email=data.email, password_hash=password_hash
        )

        # Update bio if provided
        user.bio = data.bio

        return ResponseEntity.created(self._user_to_dto(user))

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
        # In real app, would fetch user and update
        # For demo, returning mock response
        return ResponseEntity.ok(
            UserDTO(
                id=id,
                username=data.username or f"user{id}",
                email=data.email or f"user{id}@example.com",
                bio=data.bio or "Updated bio",
                active=True,
                created_at=datetime.now().isoformat(),
            )
        )

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
        return [self._user_to_dto(u) for u in users]

    @GetMapping("/stats")
    async def get_user_stats(self, min_posts: int = QueryParam(default=0)):
        """
        Get user statistics using custom SQLAlchemy query.
        Demonstrates get_connection() usage for complex queries.
        """
        return await self.user_service.get_users_with_post_stats(min_posts=min_posts)

    def _user_to_dto(self, user: User) -> UserDTO:
        """Convert User entity to UserDTO."""
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            bio=user.bio,
            active=user.active,
            created_at=user.created_at.isoformat(),
        )


@RestController("/api/posts")
class PostController:
    """REST API for blog posts."""

    def __init__(
        self,
        post_service: PostService,
        user_service: UserService,
        tag_service: TagService,
    ):
        self.post_service = post_service
        self.user_service = user_service
        self.tag_service = tag_service

    @PostMapping("/populate")
    async def populate_data(self):
        """Populate the database with sample data."""
        # Create users
        user1 = await self.user_service.create_user(
            "user1", "user1@example.com", "pass1"
        )
        user2 = await self.user_service.create_user(
            "user2", "user2@example.com", "pass2"
        )

        # Create tags
        tag1 = await self.tag_service.create_tag("Python", "python")
        tag2 = await self.tag_service.create_tag("Web Development", "web-dev")

        # Create posts
        post1 = await self.post_service.create_post(
            title="Getting Started with Mitsuki Framework",
            slug="getting-started-mitsuki",
            content="Mitsuki is a an opinionated web development framework...",
            author_id=user1.id,
        )
        post2 = await self.post_service.create_post(
            title="Advanced @Query Decorator Usage",
            slug="advanced-query-decorator-usage",
            content="The @Query decorator in Mitsuki allows you to write custom SQL queries...",
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

        return {"message": "Database populated with sample data."}

    @GetMapping("/")
    async def get_posts(
        self, page: int = QueryParam(default=0), size: int = QueryParam(default=20)
    ):
        """Get paginated list of published posts."""
        # This would typically fetch published posts
        # For demo, using search with empty query
        posts = await self.post_service.search_posts("", page=page, page_size=size)
        return {
            "posts": [self._post_to_dict(p) for p in posts],
            "page": page,
            "size": size,
        }

    @GetMapping("/public", exclude_fields=["author_id", "views"])
    async def get_public_posts(
        self, page: int = QueryParam(default=0), size: int = QueryParam(default=20)
    ):
        """Get posts with sensitive fields removed."""
        posts = await self.post_service.search_posts("", page=page, page_size=size)
        return {
            "posts": [self._post_to_dict(p) for p in posts],
            "page": page,
            "size": size,
        }

    @GetMapping("/trending")
    async def get_trending(
        self,
        days: int = QueryParam(default=7),
        min_views: int = QueryParam(default=100),
        page: int = QueryParam(default=0),
        size: int = QueryParam(default=10),
    ):
        """Get trending posts."""
        posts = await self.post_service.get_trending_posts(
            days=days, min_views=min_views, page=page, page_size=size
        )
        return {
            "posts": [self._post_to_dict(p) for p in posts],
            "page": page,
            "size": size,
        }

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
            "posts": [self._post_to_dict(p) for p in posts],
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
        return self._post_to_dict(post)

    @GetMapping("/{id}/tag-analytics")
    async def get_post_tag_analytics(self, id: int = PathVariable()):
        """
        Get tag analytics for a post using custom SQLAlchemy query.
        Demonstrates raw SQL with text() for complex analytics.
        """
        analytics = await self.post_service.get_post_tag_analytics(id)
        return {"post_id": id, "tags": analytics}

    @PostMapping("/")
    async def create_post(self, data: dict = RequestBody()):
        """Create a new post."""
        post = await self.post_service.create_post(
            title=data["title"],
            slug=data["slug"],
            content=data["content"],
            author_id=data["author_id"],
        )
        return ResponseEntity.created(self._post_to_dict(post))

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
        import os

        # Create uploads directory if it doesn't exist
        upload_dir = "uploads/posts"
        os.makedirs(upload_dir, exist_ok=True)

        # Generate filename
        filename = f"{id}_{image.filename}"
        filepath = os.path.join(upload_dir, filename)

        # Save the file
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
            "posts": [self._post_to_dict(p) for p in posts],
            "author_id": author_id,
            "page": page,
            "size": size,
        }

    def _post_to_dict(self, post: Post) -> dict:
        """Convert Post entity to dictionary."""
        return {
            "id": post.id,
            "title": post.title,
            "slug": post.slug,
            "content": post.content,
            "author_id": post.author_id,
            "views": post.views,
            "published": post.published,
            "published_at": post.published_at.isoformat()
            if post.published_at
            else None,
            "created_at": post.created_at.isoformat(),
            "updated_at": post.updated_at.isoformat(),
        }


@RestController("/api/comments")
class CommentController:
    """REST API for comments."""

    def __init__(self, comment_service: CommentService):
        self.comment_service = comment_service

    @GetMapping("/post/{post_id}")
    async def get_post_comments(
        self,
        post_id: int = PathVariable(),
        page: int = QueryParam(default=0),
        size: int = QueryParam(default=50),
    ):
        """Get comments for a post."""
        comments = await self.comment_service.get_post_comments(
            post_id=post_id, include_unapproved=False, page=page, page_size=size
        )
        return {
            "comments": [self._comment_to_dict(c) for c in comments],
            "post_id": post_id,
            "page": page,
            "size": size,
        }

    @PostMapping("/")
    async def create_comment(self, data: dict = RequestBody()):
        """Create a new comment."""
        comment = await self.comment_service.create_comment(
            post_id=data["post_id"], user_id=data["user_id"], content=data["content"]
        )
        return ResponseEntity.created(self._comment_to_dict(comment))

    @PutMapping("/{id}/approve")
    async def approve_comment(self, id: int = PathVariable()):
        """Approve a comment."""
        success = await self.comment_service.approve_comment(id)
        if not success:
            return ResponseEntity.not_found({"error": "Comment not found"})
        return {"message": "Comment approved"}

    def _comment_to_dict(self, comment: Comment) -> dict:
        """Convert Comment entity to dictionary."""
        return {
            "id": comment.id,
            "post_id": comment.post_id,
            "user_id": comment.user_id,
            "content": comment.content,
            "approved": comment.approved,
            "created_at": comment.created_at.isoformat(),
            "updated_at": comment.updated_at.isoformat(),
        }


@RestController("/api/tags")
class TagController:
    """REST API for tags."""

    def __init__(self, tag_service: TagService):
        self.tag_service = tag_service

    @GetMapping("/")
    async def get_all_tags(
        self, page: int = QueryParam(default=0), size: int = QueryParam(default=100)
    ):
        """Get all tags."""
        tags = await self.tag_service.get_all_tags(page=page, page_size=size)
        return {
            "tags": [
                {
                    "id": t.id,
                    "name": t.name,
                    "slug": t.slug,
                    "created_at": t.created_at.isoformat(),
                }
                for t in tags
            ],
            "page": page,
            "size": size,
        }

    @GetMapping("/{slug}")
    async def get_tag(self, slug: str = PathVariable()):
        """Get tag by slug."""
        tag = await self.tag_service.get_tag_by_slug(slug)
        if not tag:
            return ResponseEntity.not_found({"error": "Tag not found"})
        return {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "created_at": tag.created_at.isoformat(),
        }

    @PostMapping("/")
    async def create_tag(self, data: dict = RequestBody()):
        """Create a new tag."""
        tag = await self.tag_service.create_tag(name=data["name"], slug=data["slug"])
        return ResponseEntity.created(
            {
                "id": tag.id,
                "name": tag.name,
                "slug": tag.slug,
                "created_at": tag.created_at.isoformat(),
            }
        )
