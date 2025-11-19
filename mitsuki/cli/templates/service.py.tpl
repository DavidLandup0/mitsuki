"""
{{DOMAIN_NAME}}Service - Business logic for {{DOMAIN_NAME}}.
"""
import uuid
from typing import List, Optional
from mitsuki import Service
from ..domain.{{domain_name}} import {{DOMAIN_NAME}}
from ..repository.{{domain_name}}_repository import {{DOMAIN_NAME}}Repository


@Service()
class {{DOMAIN_NAME}}Service:
    """Service layer for {{DOMAIN_NAME}} business logic."""

    def __init__(self, repo: {{DOMAIN_NAME}}Repository):
        self.repo = repo

    async def get_all(self, page: int = 0, size: int = 100) -> List[{{DOMAIN_NAME}}]:
        """Get all {{domain_name}}s with pagination"""
        return await self.repo.find_all(page=page, size=size)

    async def get_by_id(self, id: uuid.UUID) -> Optional[{{DOMAIN_NAME}}]:
        """Get {{domain_name}} by ID"""
        return await self.repo.find_by_id(id)

    async def create(self) -> {{DOMAIN_NAME}}:
        """Create new {{domain_name}}"""
        entity = {{DOMAIN_NAME}}(id=None)
        return await self.repo.save(entity)

    async def delete(self, id: uuid.UUID) -> bool:
        """Delete {{domain_name}} by ID"""
        exists = await self.repo.exists_by_id(id)
        if not exists:
            return False
        await self.repo.delete_by_id(id)
        return True
