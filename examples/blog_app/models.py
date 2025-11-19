from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from mitsuki import Column, Entity, Field, Id


@Entity()
@dataclass
class User:
    """User entity for blog authors."""

    id: int = Id()
    username: str = ""
    email: str = Column(unique=True)
    password_hash: str = ""
    bio: str = ""
    active: bool = True
    created_at: datetime = Field(update_on_create=True)
    updated_at: datetime = Field(update_on_save=True)


@Entity()
@dataclass
class Post:
    """Blog post entity."""

    id: int = Id()
    title: str = ""
    slug: str = Column(unique=True)
    content: str = ""
    author_id: int = 0
    views: int = 0
    published: bool = False
    published_at: Optional[datetime] = None
    created_at: datetime = Field(update_on_create=True)
    updated_at: datetime = Field(update_on_save=True)


@Entity()
@dataclass
class Comment:
    """Comment entity for blog posts."""

    id: int = Id()
    post_id: int = 0
    user_id: int = 0
    content: str = ""
    approved: bool = False
    created_at: datetime = Field(update_on_create=True)
    updated_at: datetime = Field(update_on_save=True)


@Entity()
@dataclass
class Tag:
    """Tag entity for categorizing posts."""

    id: int = Id()
    name: str = Column(unique=True)
    slug: str = Column(unique=True)
    created_at: datetime = Field(update_on_create=True)


@Entity()
@dataclass
class PostTag:
    """Many-to-many relationship between posts and tags."""

    id: int = Id()
    post_id: int = 0
    tag_id: int = 0
    created_at: datetime = Field(update_on_create=True)
