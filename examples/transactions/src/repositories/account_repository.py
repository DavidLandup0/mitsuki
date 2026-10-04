from src.domain import Account

from mitsuki import CrudRepository


@CrudRepository(entity=Account)
class AccountRepository:
    pass
