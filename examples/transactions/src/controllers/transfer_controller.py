from dataclasses import asdict, dataclass
from typing import List

from src.domain import AccountNotFound, InsufficientFunds
from src.repositories.audit_repository import AuditRepository
from src.services.transfer_service import Transfer, TransferService

from mitsuki import (
    Consumes,
    GetMapping,
    PostMapping,
    RequestBody,
    ResponseEntity,
    RestController,
)


@dataclass
class TransferBatch:
    transfers: List[Transfer]


@RestController("/api")
class TransferController:
    def __init__(self, transfers: TransferService, audit: AuditRepository):
        self.transfers = transfers
        self.audit = audit

    @PostMapping("/transfers")
    @Consumes(Transfer)
    async def transfer(self, body: Transfer = RequestBody()) -> ResponseEntity:
        try:
            await self.transfers.transfer(body)
        except AccountNotFound as error:
            return ResponseEntity.not_found({"error": str(error)})
        except InsufficientFunds as error:
            return ResponseEntity.conflict({"error": str(error)})
        return ResponseEntity.ok({"status": "completed"})

    @PostMapping("/transfers/batch")
    @Consumes(TransferBatch)
    async def transfer_all(self, body: TransferBatch = RequestBody()) -> ResponseEntity:
        completed = await self.transfers.transfer_all(body.transfers)
        return ResponseEntity.ok({"completed": completed})

    @GetMapping("/audit")
    async def audit_log(self) -> ResponseEntity:
        entries = await self.audit.find_all(sort_by="id")
        return ResponseEntity.ok([asdict(e) for e in entries])
