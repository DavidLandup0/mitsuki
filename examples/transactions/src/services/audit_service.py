from src.domain import AuditEntry
from src.repositories.audit_repository import AuditRepository

from mitsuki import Propagation, Service, Transactional


@Service()
class AuditService:
    def __init__(self, entries: AuditRepository):
        self.entries = entries

    @Transactional(propagation=Propagation.REQUIRES_NEW)
    async def record(self, message: str) -> None:
        """Commits on its own, so the entry survives a rollback of the caller."""
        await self.entries.save(AuditEntry(message=message))
