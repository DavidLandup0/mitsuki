from typing import List, Optional

from src.domain import User
from src.repositories.user_repository import UserRepository

from mitsuki import Service


@Service()
class UserService:
    """
    Business logic for user management.

    Automatically instrumented - all method calls tracked for:
    - Execution time (min, max, avg)
    - Call count
    - Error rate
    - Memory usage
    """

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, username: str, email: str) -> User:
        """Create a new user. Automatically tracked by instrumentation."""
        user = User(username=username, email=email, active=True)
        return await self.user_repo.save(user)

    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID. Automatically tracked."""
        return await self.user_repo.find_by_id(user_id)

    async def get_all_users(self) -> List[User]:
        """Get all users. Automatically tracked."""
        return await self.user_repo.find_all()

    async def deactivate_user(self, user_id: int) -> Optional[User]:
        """
        Deactivate a user.

        This method is automatically instrumented, so:
        - If it raises an error, the error count increments
        - Execution time is tracked
        - Memory delta is recorded
        """
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            return None

        user.active = False
        return await self.user_repo.save(user)

    async def find_by_username(self, username: str) -> List[User]:
        return await self.user_repo.find_by_username(username)
