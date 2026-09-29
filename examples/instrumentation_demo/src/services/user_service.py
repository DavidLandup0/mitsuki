from typing import List, Optional

from src.domain import User
from src.repositories.user_repository import UserRepository

from mitsuki import Service


@Service()
class UserService:
    """
    Business logic for user management.

    Instrumented through @Instrumented on the application: every public method
    records its call count, failures and duration.
    """

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, username: str, email: str) -> User:
        user = User(username=username, email=email, active=True)
        return await self.user_repo.save(user)

    async def get_user(self, user_id: int) -> Optional[User]:
        return await self.user_repo.find_by_id(user_id)

    async def get_all_users(self) -> List[User]:
        return await self.user_repo.find_all()

    async def deactivate_user(self, user_id: int) -> Optional[User]:
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            return None

        user.active = False
        return await self.user_repo.save(user)
