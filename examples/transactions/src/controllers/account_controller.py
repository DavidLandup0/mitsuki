from dataclasses import asdict, dataclass

from src.services.account_service import AccountService

from mitsuki import (
    Consumes,
    GetMapping,
    PostMapping,
    RequestBody,
    ResponseEntity,
    RestController,
)


@dataclass
class OpenAccountRequest:
    owner: str
    balance: int


@RestController("/api/accounts")
class AccountController:
    def __init__(self, accounts: AccountService):
        self.accounts = accounts

    @PostMapping("")
    @Consumes(OpenAccountRequest)
    async def open(self, body: OpenAccountRequest = RequestBody()) -> ResponseEntity:
        account = await self.accounts.open(body.owner, body.balance)
        return ResponseEntity.created(asdict(account))

    @GetMapping("")
    async def all(self) -> ResponseEntity:
        return ResponseEntity.ok([asdict(a) for a in await self.accounts.all()])
