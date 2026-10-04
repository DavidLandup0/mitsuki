from dataclasses import dataclass
from typing import List

from src.domain import AccountNotFound, InsufficientFunds
from src.services.account_service import AccountService
from src.services.audit_service import AuditService

from mitsuki import Propagation, Service, Transactional, transaction


@dataclass
class Transfer:
    source_id: int
    target_id: int
    amount: int


@Service()
class TransferService:
    def __init__(self, accounts: AccountService, audit: AuditService):
        self.accounts = accounts
        self.audit = audit

    @Transactional()
    async def transfer(self, transfer: Transfer) -> None:
        await self.audit.record(
            f"Transfer of {transfer.amount} from {transfer.source_id} "
            f"to {transfer.target_id} requested"
        )
        await self.accounts.withdraw(transfer.source_id, transfer.amount)
        await self.accounts.deposit(transfer.target_id, transfer.amount)

    @Transactional()
    async def transfer_all(self, transfers: List[Transfer]) -> List[bool]:
        """Run every transfer that can be covered and skip the rest."""
        completed = []
        for transfer in transfers:
            try:
                async with transaction(propagation=Propagation.NESTED):
                    await self.transfer(transfer)
                completed.append(True)
            except (AccountNotFound, InsufficientFunds):
                completed.append(False)
        return completed
