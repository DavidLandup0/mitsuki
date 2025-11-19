"""
{{DOMAIN_NAME}} entity definition.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from mitsuki import Entity, UUIDv7, Field


@Entity()
@dataclass
class {{DOMAIN_NAME}}:
    """{{DOMAIN_NAME}} domain object."""
    id: uuid.UUID = UUIDv7()
    created_at: datetime = Field(update_on_create=True)
    updated_at: datetime = Field(update_on_save=True)
