from dataclasses import dataclass

from src.services.user_service import UserService

from mitsuki.web import Consumes, GetMapping, PostMapping, RequestBody, RestController
from mitsuki.web.response import ResponseEntity


@dataclass
class CreateUserRequest:
    username: str
    email: str


@RestController("/api/users")
class UserController:
    """
    REST API for user management.

    Every request is recorded in the HTTP metrics, labelled by method, route
    template and status. Each handler is also recorded as a component call.
    """

    def __init__(self, user_service: UserService):
        self.user_service = user_service

    @PostMapping("")
    @Consumes(CreateUserRequest)
    async def create_user(
        self, body: CreateUserRequest = RequestBody()
    ) -> ResponseEntity:
        user = await self.user_service.create_user(body.username, body.email)
        return ResponseEntity.created(
            {"id": user.id, "username": user.username, "email": user.email}
        )

    @GetMapping("")
    async def get_all_users(self) -> ResponseEntity:
        users = await self.user_service.get_all_users()
        return ResponseEntity.ok(
            [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "active": u.active,
                }
                for u in users
            ]
        )

    @GetMapping("/{user_id}")
    async def get_user(self, user_id: int) -> ResponseEntity:
        user = await self.user_service.get_user(user_id)
        if not user:
            return ResponseEntity.not_found({"error": "User not found"})

        return ResponseEntity.ok(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "active": user.active,
            }
        )

    @PostMapping("/{user_id}/deactivate")
    async def deactivate_user(self, user_id: int) -> ResponseEntity:
        user = await self.user_service.deactivate_user(user_id)
        if not user:
            return ResponseEntity.not_found({"error": "User not found"})

        return ResponseEntity.ok(
            {
                "id": user.id,
                "username": user.username,
                "active": user.active,
                "message": "User deactivated",
            }
        )
