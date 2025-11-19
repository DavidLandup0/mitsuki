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

    def to_dto(self):
        """Convert to UserDTO for API responses."""
        from dtos import UserDTO

        return UserDTO(
            id=self.id,
            username=self.username,
            email=self.email,
            bio=self.bio,
            active=self.active,
            created_at=self.created_at.isoformat(),
        )


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

    def to_dto(self):
        """Convert to PostDTO for API responses."""
        from dtos import PostDTO

        return PostDTO(
            id=self.id,
            title=self.title,
            slug=self.slug,
            content=self.content,
            author_id=self.author_id,
            views=self.views,
            published=self.published,
            published_at=self.published_at.isoformat() if self.published_at else None,
            created_at=self.created_at.isoformat(),
        )
