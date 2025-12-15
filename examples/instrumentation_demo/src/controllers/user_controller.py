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

    Automatically instrumented - all endpoints tracked for:
    - HTTP method distribution
    - Status code distribution
    - Request latency (p50, p95, p99)
    - Per-endpoint statistics
    """

    def __init__(self, user_service: UserService):
        self.user_service = user_service

    @PostMapping("")
    @Consumes(CreateUserRequest)
    async def create_user(
        self, body: CreateUserRequest = RequestBody()
    ) -> ResponseEntity:
        """
        Create a new user.

        Automatically tracked:
        - POST request count
        - Response time
        - 201 status code count
        """
        user = await self.user_service.create_user(body.username, body.email)
        return ResponseEntity.created(
            {"id": user.id, "username": user.username, "email": user.email}
        )

    @GetMapping("")
    async def get_all_users(self) -> ResponseEntity:
        """
        Get all users.

        Instrumentation tracks:
        - GET request count
        - Response time for list operations
        """
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
        """
        Get user by ID.

        Instrumentation tracks:
        - Per-endpoint timing
        - 404 vs 200 status codes
        """
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
        """
        Deactivate a user.

        If this endpoint throws errors, instrumentation will track:
        - Error count
        - Error rate
        - 500 status code count
        """
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
