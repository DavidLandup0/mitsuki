from dataclasses import dataclass

from mitsuki.data import Entity, Id


@Entity()
@dataclass
class Order:
    id: int = Id()
    user_id: int = 0
    product_type: str = ""
    amount: float = 0.0
    region: str = "us-east"
