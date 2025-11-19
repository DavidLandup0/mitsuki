"""
{{DOMAIN_NAME}}Repository - Data access layer for {{DOMAIN_NAME}}.
"""
from typing import Optional, List
from mitsuki import CrudRepository, Query, Modifying
from ..domain.{{domain_name}} import {{DOMAIN_NAME}}


@CrudRepository(entity={{DOMAIN_NAME}})
class {{DOMAIN_NAME}}Repository:
    """
    Repository for {{DOMAIN_NAME}} entities.

    Auto-implemented CRUD methods (you can just call these as-is):
    - save(entity) - Create or update
    - find_by_id(id) - Find by primary key
    - find_all(page, size, sort_by, sort_desc) - Paginated query
    - delete(entity) - Delete entity
    - delete_by_id(id) - Delete by ID
    - count() - Count all entities
    - exists_by_id(id) - Check existence

    Auto-generated query methods (define signature only):
    Examples:
        async def find_by_name(self, name: str) -> Optional[{{DOMAIN_NAME}}]: ...
        async def find_by_status(self, status: str) -> List[{{DOMAIN_NAME}}]: ...
        async def find_by_created_at_greater_than(self, created_at) -> List[{{DOMAIN_NAME}}]: ...

    Custom @Query methods:
        @Query("SELECT e FROM {{DOMAIN_NAME}} e WHERE e.status = :status ORDER BY e.created_at DESC")
        async def find_active_sorted(self, status: str) -> List[{{DOMAIN_NAME}}]: ...

    Custom @Modifying queries (UPDATE/DELETE):
        @Modifying
        @Query("UPDATE {{DOMAIN_NAME}} SET status = :status WHERE id = :id")
        async def update_status(self, id: int, status: str) -> int: ...

    Custom methods with direct database access:
        async def custom_complex_query(self, param: str) -> List[dict]:
            async with self.connection as conn:
                result = await conn.execute("SELECT * FROM table WHERE field = :param", {"param": param})
                return [dict(row) for row in result]
    """

    # Add your custom query methods here
    pass
