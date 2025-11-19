from datetime import datetime, timedelta
from typing import List, Optional

from models import Comment, Post, Tag, User
from repositories import (
    CommentRepository,
    PostRepository,
    PostTagRepository,
    TagRepository,
    UserRepository,
)

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

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        users = await self.user_repo.find_by_email(email)
        return users[0] if users else None

    async def get_active_users(self, page: int = 0, page_size: int = 20) -> List[User]:
        """Get paginated list of active users."""
        return await self.user_repo.find_active_users(
            active=True, limit=page_size, offset=page * page_size
        )

    async def get_users_with_post_stats(self, min_posts: int = 0):
        """Get users with their post statistics using custom SQLAlchemy query."""
        return await self.user_repo.find_users_with_post_stats(min_posts=min_posts)


@Service()
class PostService:
    """Service for blog post operations."""

    def __init__(self, post_repo: PostRepository, post_tag_repo: PostTagRepository):
        self.post_repo = post_repo
        self.post_tag_repo = post_tag_repo

    async def create_post(
        self, title: str, slug: str, content: str, author_id: int
    ) -> Post:
        """Create a new blog post."""
        post = Post(title=title, slug=slug, content=content, author_id=author_id)
        return await self.post_repo.save(post)

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

    async def get_trending_posts(
        self, days: int = 7, min_views: int = 100, page: int = 0, page_size: int = 10
    ) -> List[Post]:
        """Get trending posts from last N days."""
        since = datetime.now() - timedelta(days=days)
        return await self.post_repo.find_trending(
            since=since, min_views=min_views, limit=page_size, offset=page * page_size
        )

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

    async def cleanup_old_drafts(self, days: int = 90) -> int:
        """Delete drafts older than N days."""
        cutoff = datetime.now() - timedelta(days=days)
        return await self.post_repo.delete_old_drafts(cutoff_date=cutoff)

    async def get_post_tag_analytics(self, post_id: int):
        """Get tag analytics for a post using custom SQLAlchemy query."""
        return await self.post_repo.get_tag_analytics(post_id=post_id)


@Service()
class CommentService:
    """Service for comment operations."""

    def __init__(self, comment_repo: CommentRepository):
        self.comment_repo = comment_repo

    async def create_comment(self, post_id: int, user_id: int, content: str) -> Comment:
        """Create a new comment."""
        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            content=content,
            approved=False,  # Requires moderation
        )
        return await self.comment_repo.save(comment)

    async def get_post_comments(
        self,
        post_id: int,
        include_unapproved: bool = False,
        page: int = 0,
        page_size: int = 50,
    ) -> List[Comment]:
        """Get comments for a post."""
        return await self.comment_repo.find_post_comments(
            post_id=post_id,
            approved=not include_unapproved,
            limit=page_size,
            offset=page * page_size,
        )

    async def approve_comment(self, comment_id: int) -> bool:
        """Approve a comment."""
        comment = await self.comment_repo.find_by_id(comment_id)
        if not comment:
            return False

        comment.approved = True
        await self.comment_repo.save(comment)
        return True

    async def cleanup_spam(self, days: int = 30) -> int:
        """Delete unapproved comments older than N days."""
        cutoff = datetime.now() - timedelta(days=days)
        return await self.comment_repo.delete_spam(cutoff_date=cutoff)


@Service()
class TagService:
    """Service for tag operations."""

    def __init__(self, tag_repo: TagRepository, post_tag_repo: PostTagRepository):
        self.tag_repo = tag_repo
        self.post_tag_repo = post_tag_repo

    async def create_tag(self, name: str, slug: str) -> Tag:
        """Create a new tag."""
        tag = Tag(name=name, slug=slug)
        return await self.tag_repo.save(tag)

    async def get_tag_by_slug(self, slug: str) -> Optional[Tag]:
        """Get tag by slug."""
        tags = await self.tag_repo.find_by_slug(slug)
        return tags[0] if tags else None

    async def add_tag_to_post(self, post_id: int, tag_id: int):
        """Add a tag to a post."""
        from models import PostTag

        post_tag = PostTag(post_id=post_id, tag_id=tag_id)
        return await self.post_tag_repo.save(post_tag)

    async def get_all_tags(self, page: int = 0, page_size: int = 100) -> List[Tag]:
        """Get all tags sorted alphabetically."""
        return await self.tag_repo.find_all_sorted(
            limit=page_size, offset=page * page_size
        )
