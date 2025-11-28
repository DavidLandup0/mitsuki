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
    ):
        """GET /api/{{domain_name}}s?page=0&size=100"""
        return await self.service.get_all(page=page, size=size)

    @GetMapping("/{id}")
    async def get_by_id(self, id: str):
        """GET /api/{{domain_name}}s/123e4567-e89b-12d3-a456-426614174000"""
        entity = await self.service.get_by_id(uuid.UUID(id))
        if not entity:
            return {"error": "Not found"}, 404
        return entity

    @PostMapping("")
    async def create(self, body: dict):
        """POST /api/{{domain_name}}s"""
        entity = await self.service.create()
        return entity, 201

    @DeleteMapping("/{id}")
    async def delete(self, id: str):
        """DELETE /api/{{domain_name}}s/123e4567-e89b-12d3-a456-426614174000"""
        deleted = await self.service.delete(uuid.UUID(id))
        if not deleted:
            return {"error": "Not found"}, 404
        return {"success": True}
