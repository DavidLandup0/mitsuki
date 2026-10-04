from dataclasses import dataclass

from mitsuki import Entity, Id


@Entity()
@dataclass
class AuditEntry:
    id: int = Id()
    message: str = ""
