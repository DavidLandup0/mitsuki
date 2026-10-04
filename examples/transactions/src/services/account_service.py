from typing import List

from src.domain import Account, AccountNotFound, InsufficientFunds
from src.repositories.account_repository import AccountRepository

from mitsuki import Service, Transactional


@Service()
class AccountService:
    def __init__(self, accounts: AccountRepository):
        self.accounts = accounts

    async def open(self, owner: str, balance: int) -> Account:
        return await self.accounts.save(Account(owner=owner, balance=balance))

    async def all(self) -> List[Account]:
        return await self.accounts.find_all(sort_by="id")

    async def get(self, account_id: int) -> Account:
        account = await self.accounts.find_by_id(account_id)
        if account is None:
            raise AccountNotFound(f"Account {account_id} does not exist")
        return account

    @Transactional()
    async def withdraw(self, account_id: int, amount: int) -> Account:
        account = await self.get(account_id)
        if account.balance < amount:
            raise InsufficientFunds(
                f"Account {account_id} holds {account.balance}, not {amount}"
            )
        account.balance -= amount
        return await self.accounts.save(account)

    @Transactional()
    async def deposit(self, account_id: int, amount: int) -> Account:
        account = await self.get(account_id)
        account.balance += amount
        return await self.accounts.save(account)
