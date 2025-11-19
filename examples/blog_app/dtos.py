"""Data Transfer Objects for Blog App."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class UserDTO:
    """Public user information (output)."""

    id: int
    username: str
    email: str
    bio: str
    active: bool
    created_at: str


@dataclass
class CreateUserRequest:
    """Request to create a new user (input)."""

    username: str
    email: str
    password: str
    bio: str = ""


@dataclass
class UpdateUserRequest:
    """Request to update user information (input)."""

    username: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None


@dataclass
class PostDTO:
    """Public post information (output)."""

    id: int
    title: str
    slug: str
    content: str
    author_id: int
    views: int
    published: bool
    published_at: Optional[str]
    created_at: str


@dataclass
class CreatePostRequest:
    """Request to create a new post (input)."""

    title: str
    slug: str
    content: str


@dataclass
class UpdatePostRequest:
    """Request to update a post (input)."""

    title: Optional[str] = None
    content: Optional[str] = None
