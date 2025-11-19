from datetime import datetime
from typing import List, Optional

from models import Post, User
from repositories import PostRepository, UserRepository

from mitsuki import Service


@Service()
class UserService:
    """Service for user-related operations."""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, username: str, email: str, password_hash: str) -> User:
        """Create a new user."""
        user = User(username=username, email=email, password_hash=password_hash)
        return await self.user_repo.save(user)

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return await self.user_repo.find_by_id(user_id)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        users = await self.user_repo.find_by_email(email)
        return users[0] if users else None

    async def get_active_users(self, page: int = 0, page_size: int = 20) -> List[User]:
        """Get paginated list of active users."""
        return await self.user_repo.find_active_users(
            active=True, limit=page_size, offset=page * page_size
        )

    async def update_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        email: Optional[str] = None,
        bio: Optional[str] = None,
    ) -> Optional[User]:
        """Update user information."""
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            return None

        if username is not None:
            user.username = username
        if email is not None:
            user.email = email
        if bio is not None:
            user.bio = bio

        return await self.user_repo.save(user)

    async def get_user_stats(self, min_posts: int = 0):
        """Get users with their post statistics using custom SQLAlchemy query."""
        return await self.user_repo.get_user_stats(min_posts=min_posts)


@Service()
class PostService:
    """Service for blog post operations."""

    def __init__(self, post_repo: PostRepository):
        self.post_repo = post_repo

    async def create_post(
        self, title: str, slug: str, content: str, author_id: int
    ) -> Post:
        """Create a new blog post."""
        post = Post(title=title, slug=slug, content=content, author_id=author_id)
        return await self.post_repo.save(post)

    async def get_post_by_id(self, post_id: int) -> Optional[Post]:
        """Get post by ID."""
        return await self.post_repo.find_by_id(post_id)

    async def publish_post(self, post_id: int) -> bool:
        """Publish a blog post."""
        affected = await self.post_repo.publish_post(
            id=post_id, published_at=datetime.now()
        )
        return affected > 0

    async def get_post_by_slug(self, slug: str) -> Optional[Post]:
        """Get post by slug and increment view count."""
        posts = await self.post_repo.find_by_slug(slug)
        if not posts:
            return None

        post = posts[0]
        await self.post_repo.increment_views(post.id)
        post.views += 1
        return post

    async def get_author_posts(
        self, author_id: int, published: bool = True, page: int = 0, page_size: int = 20
    ) -> List[Post]:
        """Get posts by author."""
        return await self.post_repo.find_by_author_and_status(
            author_id=author_id,
            published=published,
            limit=page_size,
            offset=page * page_size,
        )

    async def search_posts(
        self, query: str, page: int = 0, page_size: int = 20
    ) -> List[Post]:
        """Search published posts by title/content."""
        search_term = f"%{query}%"
        return await self.post_repo.search_posts(
            search=search_term, published=True, limit=page_size, offset=page * page_size
        )

    async def get_post_analytics(self):
        """Get post analytics using custom SQLAlchemy query."""
        return await self.post_repo.get_post_analytics()
