from dataclasses import dataclass

from mitsuki.data import Column, Entity, Id


@Entity()
@dataclass
class User:
    id: int = Id()
    username: str = Column(unique=True, default="")
    email: str = Column(unique=True, default="")
    active: bool = True
