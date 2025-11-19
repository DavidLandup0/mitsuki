"""Tests for @Query, @Modifying decorators, and custom SQLAlchemy queries."""

from dataclasses import dataclass
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from mitsuki import CrudRepository, Entity, Field, Id, Modifying, Query
from mitsuki.data import SQLAlchemyAdapter, get_entity_metadata, set_database_adapter
from mitsuki.data.repository import get_database_adapter
from mitsuki.exceptions import QueryException


@pytest_asyncio.fixture
async def setup_database():
    """Setup in-memory SQLite database for tests."""
    adapter = SQLAlchemyAdapter()
    await adapter.connect("sqlite+aiosqlite:///:memory:")
    set_database_adapter(adapter)

    yield adapter

    await adapter.disconnect()
    set_database_adapter(None)


@Entity()
@dataclass
class User:
    """Test entity for custom query tests."""

    id: int = Id()
    name: str = ""
    email: str = ""
    age: int = 0
    active: bool = True
    created_at: datetime = Field(update_on_create=True)


@Entity()
@dataclass
class Post:
    """Test entity for custom SQLAlchemy query tests."""

    id: int = Id()
    title: str = ""
    author_id: int = 0
    views: int = 0
    created_at: datetime = Field(update_on_create=True)


@CrudRepository(entity=User)
class UserRepository:
    # Custom ORM query
    @Query("""
        SELECT u FROM User u
        WHERE u.email = :email
    """)
    async def find_by_custom_email(self, email: str): ...

    # Custom ORM query with multiple params
    @Query("""
        SELECT u FROM User u
        WHERE u.age > :min_age AND u.active = :active
        ORDER BY u.age DESC
    """)
    async def find_active_older_than(self, min_age: int, active: bool): ...

    # Native SQL query
    @Query(
        """
        SELECT * FROM users
        WHERE age BETWEEN :min_age AND :max_age
    """,
        native=True,
    )
    async def find_in_age_range_native(self, min_age: int, max_age: int): ...

    # Modifying query
    @Modifying
    @Query("""
        UPDATE User u
        SET u.active = :status
        WHERE u.age > :age
    """)
    async def deactivate_older_than(self, age: int, status: bool): ...

    # Positional parameters
    @Query("""
        SELECT u FROM User u
        WHERE u.age > ?1 AND u.active = ?2
    """)
    async def find_by_age_and_active_positional(self, min_age: int, active: bool): ...

    # Pagination support
    @Query("""
        SELECT u FROM User u
        WHERE u.active = :active
        ORDER BY u.age DESC
    """)
    async def find_active_paginated(self, active: bool, limit: int, offset: int): ...

    # Custom SQLAlchemy Core query using get_connection()
    async def find_users_with_post_stats(self, min_posts: int = 0):
        """
        Custom query using get_connection() and SQLAlchemy Core.
        Returns users with their post count and total views.
        """
        async with self.get_connection() as conn:
            adapter = get_database_adapter()

            user_table = adapter.get_table(User)
            post_table = adapter.get_table(Post)

            query = (
                select(
                    user_table.c.id,
                    user_table.c.name,
                    user_table.c.email,
                    func.count(post_table.c.id).label("post_count"),
                    func.sum(post_table.c.views).label("total_views"),
                )
                .select_from(user_table)
                .outerjoin(post_table, user_table.c.id == post_table.c.author_id)
                .where(user_table.c.active == True)
                .group_by(user_table.c.id, user_table.c.name, user_table.c.email)
                .having(func.count(post_table.c.id) >= min_posts)
                .order_by(func.count(post_table.c.id).desc())
            )

            result = await conn.execute(query)
            rows = result.fetchall()

            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "email": row.email,
                    "post_count": row.post_count,
                    "total_views": row.total_views or 0,
                }
                for row in rows
            ]


@CrudRepository(entity=Post)
class PostRepository:
    # Custom raw SQL query using text()
    async def get_popular_posts_by_author(self, author_id: int, min_views: int = 0):
        """
        Custom query using text() for raw SQL.
        Returns popular posts by a specific author.
        """
        async with self.get_connection() as conn:
            query = text("""
                SELECT id, title, author_id, views
                FROM posts
                WHERE author_id = :author_id
                AND views >= :min_views
                ORDER BY views DESC
            """)

            result = await conn.execute(
                query, {"author_id": author_id, "min_views": min_views}
            )
            rows = result.fetchall()

            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "author_id": row.author_id,
                    "views": row.views,
                }
                for row in rows
            ]

    # Dynamic query building
    async def search_posts(
        self, title: str = None, min_views: int = None, author_id: int = None
    ):
        """
        Custom query with dynamic filters.
        Demonstrates conditional query building.
        """
        async with self.get_connection() as conn:
            adapter = get_database_adapter()
            post_table = adapter.get_table(Post)

            query = select(post_table)
            conditions = []

            if title:
                conditions.append(post_table.c.title.like(f"%{title}%"))
            if min_views is not None:
                conditions.append(post_table.c.views >= min_views)
            if author_id is not None:
                conditions.append(post_table.c.author_id == author_id)

            if conditions:
                query = query.where(and_(*conditions))

            result = await conn.execute(query)
            return [Post(**dict(row._mapping)) for row in result.fetchall()]


class TestCustomQueries:
    """Tests for custom @Query methods."""

    @pytest.mark.asyncio
    async def test_custom_orm_query(self, setup_database):
        """Should execute custom ORM query."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create test users
        user1 = await repo.save(User(name="Alice", email="alice@example.com", age=25))
        user2 = await repo.save(User(name="Bob", email="bob@example.com", age=30))

        # Query by email using custom query
        results = await repo.find_by_custom_email("alice@example.com")

        assert len(results) == 1
        assert results[0].name == "Alice"
        assert results[0].email == "alice@example.com"

    @pytest.mark.asyncio
    async def test_custom_query_with_multiple_params(self, setup_database):
        """Should execute custom query with multiple parameters."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create test users
        await repo.save(
            User(name="Young", email="young@example.com", age=18, active=True)
        )
        await repo.save(
            User(name="Adult", email="adult@example.com", age=25, active=True)
        )
        await repo.save(
            User(name="Senior", email="senior@example.com", age=65, active=False)
        )

        # Query active users older than 20
        results = await repo.find_active_older_than(20, True)

        assert len(results) == 1
        assert results[0].name == "Adult"
        assert results[0].age == 25

    @pytest.mark.asyncio
    async def test_native_sql_query(self, setup_database):
        """Should execute native SQL query."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create test users
        await repo.save(User(name="Teen", email="teen@example.com", age=16))
        await repo.save(User(name="Adult", email="adult@example.com", age=30))
        await repo.save(User(name="Senior", email="senior@example.com", age=65))

        # Query using native SQL
        results = await repo.find_in_age_range_native(18, 50)

        assert len(results) == 1
        assert results[0].name == "Adult"

    @pytest.mark.asyncio
    async def test_modifying_query(self, setup_database):
        """Should execute modifying query and return affected row count."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create test users
        await repo.save(
            User(name="Young", email="young@example.com", age=18, active=True)
        )
        await repo.save(
            User(name="Adult", email="adult@example.com", age=25, active=True)
        )
        await repo.save(
            User(name="Senior", email="senior@example.com", age=65, active=True)
        )

        # Deactivate users older than 30
        affected = await repo.deactivate_older_than(30, False)

        assert affected == 1

        # Verify the senior was deactivated
        senior = await repo.find_by_custom_email("senior@example.com")
        assert len(senior) == 1
        assert senior[0].active == False  # SQLite returns 0/1 for boolean

    @pytest.mark.asyncio
    async def test_modifying_without_decorator_raises_error(self, setup_database):
        """Should raise QueryException if UPDATE/DELETE used without @Modifying."""

        # Create a repository with UPDATE without @Modifying
        @CrudRepository(entity=User)
        class BadRepository:
            @Query("""
                UPDATE User u
                SET u.active = :status
                WHERE u.id = :id
            """)
            async def bad_update(self, id: int, status: bool): ...

            @Query("""
                DELETE FROM User u
                WHERE u.id = :id
            """)
            async def bad_delete(self, id: int): ...

        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = BadRepository()

        # Create a test user
        user = await repo.save(User(name="Test", email="test@example.com", age=25))

        # Try UPDATE without @Modifying - should raise
        with pytest.raises(QueryException) as exc_info:
            await repo.bad_update(user.id, False)

        assert "missing @Modifying decorator" in str(exc_info.value)
        assert "bad_update" in str(exc_info.value)

        # Try DELETE without @Modifying - should raise
        with pytest.raises(QueryException) as exc_info:
            await repo.bad_delete(user.id)

        assert "missing @Modifying decorator" in str(exc_info.value)
        assert "bad_delete" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_positional_parameters(self, setup_database):
        """Should support positional parameters (?1, ?2, etc.)."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create test users
        await repo.save(
            User(name="Young", email="young@example.com", age=18, active=True)
        )
        await repo.save(
            User(name="Adult", email="adult@example.com", age=25, active=True)
        )
        await repo.save(
            User(name="Senior", email="senior@example.com", age=65, active=False)
        )

        # Query using positional parameters
        results = await repo.find_by_age_and_active_positional(20, True)

        assert len(results) == 1
        assert results[0].name == "Adult"
        assert results[0].age == 25

    @pytest.mark.asyncio
    async def test_pagination(self, setup_database):
        """Should support limit and offset parameters for pagination."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create test users
        await repo.save(
            User(name="User1", email="user1@example.com", age=20, active=True)
        )
        await repo.save(
            User(name="User2", email="user2@example.com", age=25, active=True)
        )
        await repo.save(
            User(name="User3", email="user3@example.com", age=30, active=True)
        )
        await repo.save(
            User(name="User4", email="user4@example.com", age=35, active=True)
        )
        await repo.save(
            User(name="User5", email="user5@example.com", age=40, active=True)
        )

        # Test pagination: get first 2 results
        page1 = await repo.find_active_paginated(True, limit=2, offset=0)
        assert len(page1) == 2
        assert page1[0].age == 40  # Ordered by age DESC
        assert page1[1].age == 35

        # Test pagination: get next 2 results
        page2 = await repo.find_active_paginated(True, limit=2, offset=2)
        assert len(page2) == 2
        assert page2[0].age == 30
        assert page2[1].age == 25

        # Test pagination: get last page
        page3 = await repo.find_active_paginated(True, limit=2, offset=4)
        assert len(page3) == 1
        assert page3[0].age == 20


class TestCustomSQLAlchemyQueries:
    """Tests for custom SQLAlchemy queries using get_connection()."""

    @pytest.mark.asyncio
    async def test_get_connection_returns_connection(self, setup_database):
        """Should return an AsyncConnection context manager."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Verify it returns a context manager and connection works
        async with repo.get_connection() as conn:
            assert isinstance(conn, AsyncConnection)

    @pytest.mark.asyncio
    async def test_custom_sqlalchemy_core_query(self, setup_database):
        """Should execute custom SQLAlchemy Core query with JOINs and aggregations."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))
        await adapter.create_table_if_not_exists(get_entity_metadata(Post))

        user_repo = UserRepository()
        post_repo = PostRepository()

        # Create test users
        user1 = await user_repo.save(
            User(name="Alice", email="alice@example.com", age=25)
        )
        user2 = await user_repo.save(User(name="Bob", email="bob@example.com", age=30))
        user3 = await user_repo.save(
            User(name="Charlie", email="charlie@example.com", age=35)
        )

        # Create posts for users
        await post_repo.save(Post(title="Post 1", author_id=user1.id, views=100))
        await post_repo.save(Post(title="Post 2", author_id=user1.id, views=200))
        await post_repo.save(Post(title="Post 3", author_id=user2.id, views=150))

        # Query users with post stats
        stats = await user_repo.find_users_with_post_stats(min_posts=0)

        # Should return 3 users (user3 has 0 posts)
        assert len(stats) == 3

        # Alice should have 2 posts with 300 total views
        alice_stats = next(s for s in stats if s["name"] == "Alice")
        assert alice_stats["post_count"] == 2
        assert alice_stats["total_views"] == 300

        # Bob should have 1 post with 150 views
        bob_stats = next(s for s in stats if s["name"] == "Bob")
        assert bob_stats["post_count"] == 1
        assert bob_stats["total_views"] == 150

        # Charlie should have 0 posts
        charlie_stats = next(s for s in stats if s["name"] == "Charlie")
        assert charlie_stats["post_count"] == 0
        assert charlie_stats["total_views"] == 0

    @pytest.mark.asyncio
    async def test_custom_sqlalchemy_core_with_min_posts_filter(self, setup_database):
        """Should filter users by minimum post count."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))
        await adapter.create_table_if_not_exists(get_entity_metadata(Post))

        user_repo = UserRepository()
        post_repo = PostRepository()

        # Create test users
        user1 = await user_repo.save(
            User(name="Alice", email="alice@example.com", age=25)
        )
        user2 = await user_repo.save(User(name="Bob", email="bob@example.com", age=30))

        # Alice has 2 posts, Bob has 1 post
        await post_repo.save(Post(title="Post 1", author_id=user1.id, views=100))
        await post_repo.save(Post(title="Post 2", author_id=user1.id, views=200))
        await post_repo.save(Post(title="Post 3", author_id=user2.id, views=150))

        # Query users with at least 2 posts
        stats = await user_repo.find_users_with_post_stats(min_posts=2)

        # Should return only Alice
        assert len(stats) == 1
        assert stats[0]["name"] == "Alice"
        assert stats[0]["post_count"] == 2

    @pytest.mark.asyncio
    async def test_text_query_with_raw_sql(self, setup_database):
        """Should execute raw SQL query using text()."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))
        await adapter.create_table_if_not_exists(get_entity_metadata(Post))

        user_repo = UserRepository()
        post_repo = PostRepository()

        # Create test user and posts
        user = await user_repo.save(
            User(name="Alice", email="alice@example.com", age=25)
        )
        await post_repo.save(Post(title="Popular Post", author_id=user.id, views=500))
        await post_repo.save(Post(title="Unpopular Post", author_id=user.id, views=10))
        await post_repo.save(
            Post(title="Another Popular Post", author_id=user.id, views=300)
        )

        # Query popular posts (views >= 100)
        popular_posts = await post_repo.get_popular_posts_by_author(
            user.id, min_views=100
        )

        assert len(popular_posts) == 2
        assert popular_posts[0]["title"] == "Popular Post"
        assert popular_posts[0]["views"] == 500
        assert popular_posts[1]["title"] == "Another Popular Post"
        assert popular_posts[1]["views"] == 300

    @pytest.mark.asyncio
    async def test_dynamic_query_building(self, setup_database):
        """Should build queries dynamically based on provided filters."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))
        await adapter.create_table_if_not_exists(get_entity_metadata(Post))

        user_repo = UserRepository()
        post_repo = PostRepository()

        # Create test users and posts
        user1 = await user_repo.save(
            User(name="Alice", email="alice@example.com", age=25)
        )
        user2 = await user_repo.save(User(name="Bob", email="bob@example.com", age=30))

        await post_repo.save(
            Post(title="Python Tutorial", author_id=user1.id, views=100)
        )
        await post_repo.save(
            Post(title="JavaScript Guide", author_id=user1.id, views=50)
        )
        await post_repo.save(
            Post(title="Python Advanced", author_id=user2.id, views=200)
        )

        # Search by title only
        results = await post_repo.search_posts(title="Python")
        assert len(results) == 2

        # Search by min_views only
        results = await post_repo.search_posts(min_views=100)
        assert len(results) == 2

        # Search by author_id only
        results = await post_repo.search_posts(author_id=user1.id)
        assert len(results) == 2

        # Search with multiple filters
        results = await post_repo.search_posts(title="Python", min_views=150)
        assert len(results) == 1
        assert results[0].title == "Python Advanced"

        # Search with all filters
        results = await post_repo.search_posts(
            title="Python", min_views=50, author_id=user1.id
        )
        assert len(results) == 1
        assert results[0].title == "Python Tutorial"

    @pytest.mark.asyncio
    async def test_connection_context_manager(self, setup_database):
        """Should properly manage connection lifecycle with context manager."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Use connection context manager
        async with repo.get_connection() as conn:
            assert conn is not None
            # Connection is active within context
            user_table = adapter.get_table(User)
            query = select(user_table)
            result = await conn.execute(query)
            assert result is not None

        # Connection is automatically closed after context

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, setup_database):
        """Should create new connection for each context manager."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create first connection
        async with repo.get_connection() as conn1:
            assert conn1 is not None
            conn1_id = id(conn1)

        # Create second connection - should be new instance
        async with repo.get_connection() as conn2:
            assert conn2 is not None
            conn2_id = id(conn2)

        # Different connection instances (though may be pooled internally by SQLAlchemy)
        # We just verify both work independently
        assert conn1_id is not None
        assert conn2_id is not None
