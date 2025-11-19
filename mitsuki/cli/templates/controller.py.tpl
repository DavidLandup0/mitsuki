"""
{{DOMAIN_NAME}}Controller - REST API endpoints for {{DOMAIN_NAME}}.
"""
import uuid
from typing import List
from mitsuki import RestController, GetMapping, PostMapping, DeleteMapping, QueryParam
from ..service.{{domain_name}}_service import {{DOMAIN_NAME}}Service


@RestController("/api/{{domain_name}}s")
class {{DOMAIN_NAME}}Controller:
    """REST API controller for {{DOMAIN_NAME}} resources."""

    def __init__(self, service: {{DOMAIN_NAME}}Service):
        self.service = service

    @GetMapping("")
    async def list_all(
        self,
        page: int = QueryParam(default=0),
        size: int = QueryParam(default=100)
    ) -> List[dict]:
        """GET /api/{{domain_name}}s?page=0&size=100"""
        entities = await self.service.get_all(page=page, size=size)
        return [self._to_dict(e) for e in entities]

    @GetMapping("/{id}")
    async def get_by_id(self, id: str) -> dict:
        """GET /api/{{domain_name}}s/123e4567-e89b-12d3-a456-426614174000"""
        entity = await self.service.get_by_id(uuid.UUID(id))
        if not entity:
            return {"error": "Not found"}, 404
        return self._to_dict(entity)

    @PostMapping("")
    async def create(self, body: dict) -> dict:
        """POST /api/{{domain_name}}s"""
        entity = await self.service.create()
        return self._to_dict(entity), 201

    @DeleteMapping("/{id}")
    async def delete(self, id: str) -> dict:
        """DELETE /api/{{domain_name}}s/123e4567-e89b-12d3-a456-426614174000"""
        deleted = await self.service.delete(uuid.UUID(id))
        if not deleted:
            return {"error": "Not found"}, 404
        return {"success": True}

    def _to_dict(self, entity) -> dict:
        """Convert entity to dict for JSON response"""
        return {
            "id": str(entity.id),
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
