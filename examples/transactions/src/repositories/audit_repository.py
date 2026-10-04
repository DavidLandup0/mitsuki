from src.domain import AuditEntry

from mitsuki import CrudRepository


@CrudRepository(entity=AuditEntry)
class AuditRepository:
    pass
