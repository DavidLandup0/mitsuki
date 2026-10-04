from dataclasses import dataclass

from mitsuki import Column, Entity, Id


@Entity()
@dataclass
class Account:
    id: int = Id()
    owner: str = Column(unique=True, default="")
    balance: int = 0


class AccountNotFound(Exception):
    pass


class InsufficientFunds(Exception):
    pass
