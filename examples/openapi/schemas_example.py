from dataclasses import dataclass
from enum import Enum

from mitsuki import Application, GetMapping, PostMapping, RestController


class Status(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


@dataclass
class Address:
    street: str
    city: str
    country: str


@dataclass
class User:
    name: str
    email: str
    status: Status
    address: Address


@dataclass
class CreateUserRequest:
    name: str
    email: str
    status: Status


@RestController("/users")
class UserController:
    @GetMapping("/{id}")
    async def get_user(self, id: int) -> User:
        """Get user by ID."""
        return User(
            name="John Doe",
            email="john@example.com",
            status=Status.ACTIVE,
            address=Address(street="123 Main St", city="NYC", country="USA"),
        )

    @PostMapping("/")
    async def create_user(self, request: CreateUserRequest) -> User:
        """Create a new user."""
        return User(
            name=request.name,
            email=request.email,
            status=request.status,
            address=Address(street="", city="", country=""),
        )


@Application
class SchemasExampleApp:
    pass


if __name__ == "__main__":
    SchemasExampleApp.run()
