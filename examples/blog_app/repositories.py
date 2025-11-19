from datetime import datetime

from models import Post, User
from sqlalchemy import func, select

from mitsuki import CrudRepository, Modifying, Query
from mitsuki.data.repository import get_database_adapter


@CrudRepository(entity=User)
class UserRepository:
    """Repository for User entity."""

    # Query DSL methods
    async def find_by_email(self, email: str): ...
    async def find_by_username(self, username: str): ...
    async def count_by_active(self, active: bool) -> int: ...

    # Custom query: Find active users
    @Query("""
        SELECT u FROM User u
        WHERE u.active = :active
        ORDER BY u.created_at DESC
    """)
    async def find_active_users(self, active: bool, limit: int, offset: int): ...

    # Custom SQLAlchemy query: User statistics
    async def get_user_stats(self, min_posts: int = 0):
        """
        Example of using get_connection() for custom SQLAlchemy Core queries.
        Gets user statistics with post counts and total views.
        """
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

            return [
                {
                    "id": row.id,
                    "username": row.username,
                    "email": row.email,
                    "post_count": row.post_count,
                    "total_views": row.total_views or 0,
                }
                for row in rows
            ]


@CrudRepository(entity=Post)
class PostRepository:
    """Repository for Post entity with custom queries."""

    # Query DSL methods
    async def find_by_slug(self, slug: str): ...
    async def find_by_author_id(self, author_id: int): ...
    async def count_by_published(self, published: bool) -> int: ...

    # Custom query: Find posts by author and status
    @Query("""
        SELECT p FROM Post p
        WHERE p.author_id = ?1
        AND p.published = ?2
        ORDER BY p.created_at DESC
    """)
    async def find_by_author_and_status(
        self, author_id: int, published: bool, limit: int, offset: int
    ): ...

    # Search posts by title/content
    @Query("""
        SELECT p FROM Post p
        WHERE (p.title LIKE :search OR p.content LIKE :search)
        AND p.published = :published
        ORDER BY p.published_at DESC
    """)
    async def search_posts(
        self, search: str, published: bool, limit: int, offset: int
    ): ...

    # Increment view count
    @Modifying
    @Query("UPDATE Post p SET p.views = p.views + 1 WHERE p.id = :id")
    async def increment_views(self, id: int) -> int: ...

    # Publish a post
    @Modifying
    @Query("""
        UPDATE Post p
        SET p.published = true, p.published_at = :published_at
        WHERE p.id = :id
    """)
    async def publish_post(self, id: int, published_at: datetime) -> int: ...

    # Custom SQLAlchemy query: Post analytics
    async def get_post_analytics(self):
        """
        Example of analytics using get_connection().
        Gets aggregate statistics across all posts.
        """
        async with self.get_connection() as conn:
            adapter = get_database_adapter()
            post_table = adapter.get_table(Post)

            query = select(
                func.count(post_table.c.id).label("total_posts"),
                func.count(post_table.c.id)
                .filter(post_table.c.published == True)
                .label("published_posts"),
                func.sum(post_table.c.views).label("total_views"),
                func.avg(post_table.c.views).label("avg_views"),
            )

            result = await conn.execute(query)
            row = result.fetchone()

            return {
                "total_posts": row.total_posts or 0,
                "published_posts": row.published_posts or 0,
                "total_views": row.total_views or 0,
                "avg_views": float(row.avg_views) if row.avg_views else 0.0,
            }
