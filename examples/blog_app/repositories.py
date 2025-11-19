from datetime import datetime

from models import Comment, Post, PostTag, Tag, User
from sqlalchemy import func, select, text

from mitsuki import CrudRepository, Modifying, Query


@CrudRepository(entity=User)
class UserRepository:
    """Repository for User entity."""

    # Query DSL methods
    async def find_by_email(self, email: str): ...
    async def find_by_username(self, username: str): ...
    async def count_by_active(self, active: bool) -> int: ...

    # Custom query: Find users with most posts
    @Query("""
        SELECT u FROM User u
        WHERE u.active = :active
        ORDER BY u.created_at DESC
    """)
    async def find_active_users(self, active: bool, limit: int, offset: int): ...

    # Custom SQLAlchemy query: Find users with post stats
    async def find_users_with_post_stats(self, min_posts: int = 0):
        """
        Example of using get_connection() for custom SQLAlchemy Core queries.
        This demonstrates a complex JOIN query that can't easily be done with @Query.
        """
        from mitsuki.data.repository import get_database_adapter

        async with self.get_connection() as conn:
            adapter = get_database_adapter()

            # Get SQLAlchemy Table objects
            user_table = adapter.get_table(User)
            post_table = adapter.get_table(Post)

            # Build complex query with SQLAlchemy Core
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

            # Return as list of dicts
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

    # Custom query: Find trending posts (recent + high views)
    @Query("""
        SELECT p FROM Post p
        WHERE p.published = true
        AND p.published_at > :since
        AND p.views > :min_views
        ORDER BY p.views DESC, p.published_at DESC
    """)
    async def find_trending(
        self, since: datetime, min_views: int, limit: int, offset: int
    ): ...

    # Custom query with positional params
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

    # Delete old unpublished drafts
    @Modifying
    @Query("""
        DELETE FROM Post p
        WHERE p.published = false
        AND p.created_at < :cutoff_date
    """)
    async def delete_old_drafts(self, cutoff_date: datetime) -> int: ...

    # Custom SQLAlchemy query: Complex analytics query
    async def get_tag_analytics(self, post_id: int):
        """
        Example of complex analytics using raw SQL via get_connection().
        Gets all tags for a post along with how many other posts share those tags.
        """
        async with self.get_connection() as conn:
            # Use text() for raw SQL when needed
            query = text("""
                SELECT
                    t.id,
                    t.name,
                    t.slug,
                    COUNT(DISTINCT pt2.post_id) as related_post_count
                FROM post_tag pt1
                JOIN tag t ON pt1.tag_id = t.id
                LEFT JOIN post_tag pt2 ON t.id = pt2.tag_id AND pt2.post_id != :post_id
                WHERE pt1.post_id = :post_id
                GROUP BY t.id, t.name, t.slug
                ORDER BY related_post_count DESC
            """)

            result = await conn.execute(query, {"post_id": post_id})
            rows = result.fetchall()

            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "slug": row.slug,
                    "related_post_count": row.related_post_count,
                }
                for row in rows
            ]


@CrudRepository(entity=Comment)
class CommentRepository:
    """Repository for Comment entity."""

    # Query DSL methods
    async def find_by_post_id(self, post_id: int): ...
    async def find_by_user_id(self, user_id: int): ...
    async def count_by_approved(self, approved: bool) -> int: ...

    # Find approved comments for a post
    @Query("""
        SELECT c FROM Comment c
        WHERE c.post_id = :post_id
        AND c.approved = :approved
        ORDER BY c.created_at DESC
    """)
    async def find_post_comments(
        self, post_id: int, approved: bool, limit: int, offset: int
    ): ...

    # Approve all comments for a post
    @Modifying
    @Query("UPDATE Comment c SET c.approved = true WHERE c.post_id = :post_id")
    async def approve_all_for_post(self, post_id: int) -> int: ...

    # Delete spam comments
    @Modifying
    @Query("""
        DELETE FROM Comment c
        WHERE c.approved = false
        AND c.created_at < :cutoff_date
    """)
    async def delete_spam(self, cutoff_date: datetime) -> int: ...


@CrudRepository(entity=Tag)
class TagRepository:
    """Repository for Tag entity."""

    # Query DSL methods
    async def find_by_slug(self, slug: str): ...
    async def find_by_name(self, name: str): ...

    # Find popular tags (most used)
    @Query("""
        SELECT t FROM Tag t
        ORDER BY t.name ASC
    """)
    async def find_all_sorted(self, limit: int, offset: int): ...


@CrudRepository(entity=PostTag)
class PostTagRepository:
    """Repository for PostTag junction table."""

    # Query DSL methods
    async def find_by_post_id(self, post_id: int): ...
    async def find_by_tag_id(self, tag_id: int): ...

    # Delete all tags for a post
    @Modifying
    @Query("DELETE FROM PostTag pt WHERE pt.post_id = :post_id")
    async def delete_post_tags(self, post_id: int) -> int: ...
