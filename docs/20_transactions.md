# Transactions

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Propagation](#propagation)
- [Rollback Rules](#rollback-rules)
- [Isolation Levels](#isolation-levels)
- [Programmatic Transactions](#programmatic-transactions)
- [Class-Level and Repository Usage](#class-level-and-repository-usage)
- [Custom Queries Inside a Transaction](#custom-queries-inside-a-transaction)
- [Limitations](#limitations)
- [Coming From Spring](#coming-from-spring)

## Overview

Without a transaction, every repository call commits on its own. In the method below, if the second `save()` fails, the first one has already been committed and money disappears:

```python
@Service()
class TransferService:
    def __init__(self, accounts: AccountRepository):
        self.accounts = accounts

    async def transfer(self, source_id: int, target_id: int, amount: int):
        source = await self.accounts.find_by_id(source_id)
        target = await self.accounts.find_by_id(target_id)
        source.balance -= amount
        await self.accounts.save(source)  # committed immediately
        target.balance += amount
        await self.accounts.save(target)  # if this fails, source stays debited
```

`@Transactional` runs the whole method in one database transaction: every repository call inside it uses the same connection, and the changes are committed together when the method returns, or rolled back together when it raises.

Mitsuki only decides where transactions begin and end. The transactions themselves - atomicity, locking, isolation and savepoints - are provided by your database, through SQLAlchemy.

## Getting Started

Add `@Transactional()` to an async method of a `@Service`, `@Repository`, `@CrudRepository` or any other component:

```python
from mitsuki import Service, Transactional

@Service()
class TransferService:
    def __init__(self, accounts: AccountRepository):
        self.accounts = accounts

    @Transactional()
    async def transfer(self, source_id: int, target_id: int, amount: int):
        source = await self.accounts.find_by_id(source_id)
        target = await self.accounts.find_by_id(target_id)
        source.balance -= amount
        await self.accounts.save(source)
        target.balance += amount
        await self.accounts.save(target)
```

- A normal return commits.
- Any exception rolls back and is re-raised. This includes `asyncio.CancelledError`, so a cancelled request never commits.
- Repository methods need no changes: built-in methods, Query DSL methods, `@Query` methods and `get_connection()` all join the transaction in progress.

The transaction follows the call chain, however deep. A repository called from a helper called from the transactional method still runs inside the transaction.

## Propagation

Propagation decides what a transactional method does when it is called while a transaction is already in progress.

```python
from mitsuki import Propagation, Transactional
```

### REQUIRED (default)

Join the transaction in progress, or begin one if there is none. Nested calls share one transaction, so an outer rollback undoes everything:

```python
@Service()
class OrderService:
    @Transactional()
    async def place(self, order: Order):
        await self.orders.save(order)
        await self.inventory.reserve(order.items)  # joins this transaction

@Service()
class InventoryService:
    @Transactional()
    async def reserve(self, items):
        ...
```

When a joined method fails, the shared transaction is marked rollback-only. If the outer method catches that exception and returns normally, the transaction is still rolled back and `UnexpectedRollbackException` is raised, so the caller never believes the work was saved:

```python
@Transactional()
async def place(self, order: Order):
    await self.orders.save(order)
    try:
        await self.inventory.reserve(order.items)  # raises
    except OutOfStock:
        pass
    # leaving the method raises UnexpectedRollbackException; nothing is saved
```

To continue after a failed step, use `NESTED` for that step instead.

### REQUIRES_NEW

Suspend the transaction in progress and run in a new, independent one on a separate connection. The new transaction commits or rolls back on its own, regardless of the outer one. This is typically used for audit logs that must persist even when the operation they record fails:

```python
@Service()
class AuditService:
    @Transactional(propagation=Propagation.REQUIRES_NEW)
    async def record(self, message: str):
        await self.audit.save(AuditLog(message=message))

@Service()
class TransferService:
    @Transactional()
    async def transfer(self, source_id: int, target_id: int, amount: int):
        await self.audit_service.record(f"transfer {source_id} -> {target_id}")
        ...
        raise InsufficientFunds()  # the transfer rolls back; the audit entry stays
```

The suspended transaction keeps its own connection while the new one runs, so each `REQUIRES_NEW` call holds a second pooled connection.

### NESTED

Run inside the transaction in progress, behind a savepoint. If the nested method fails, only its own work is rolled back and the outer transaction continues. If the outer transaction later rolls back, the nested work is rolled back with it. With no transaction in progress, `NESTED` begins one, like `REQUIRED`.

```python
@Service()
class ImportService:
    @Transactional()
    async def import_all(self, rows):
        for row in rows:
            try:
                await self.import_row(row)
            except InvalidRow:
                pass  # this row's changes are undone; the others are kept

    @Transactional(propagation=Propagation.NESTED)
    async def import_row(self, row):
        ...
```

## Rollback Rules

Every exception rolls back by default. List exceptions that should commit the work done so far in `no_rollback_for`. Subclasses of the listed types match too. The exception is re-raised either way:

```python
@Transactional(no_rollback_for=(PaymentDeclined,))
async def checkout(self, cart: Cart):
    order = await self.orders.save(Order.from_cart(cart, status="pending"))
    await self.payments.charge(order)  # PaymentDeclined: the pending order is kept
```

A joined method that fails with an exception from its own `no_rollback_for` does not mark the shared transaction rollback-only.

## Isolation Levels

Isolation decides how much of other transactions' work a transaction can see while it runs:

```python
from mitsuki import Isolation, Transactional

@Transactional(isolation=Isolation.SERIALIZABLE)
async def allocate_seat(self, flight_id: int, passenger: str):
    ...
```

| Level | Behaviour | PostgreSQL | MySQL | SQLite |
|---|---|---|---|---|
| `READ_UNCOMMITTED` | May see other transactions' uncommitted changes ("dirty reads") | - | Yes | Yes |
| `READ_COMMITTED` | Sees changes as soon as other transactions commit | Default | Yes | - |
| `REPEATABLE_READ` | Rows already read do not change under you | Yes | Default | - |
| `SERIALIZABLE` | Behaves as if transactions ran one at a time | Yes | Yes | Default |

- Isolation applies only where a transaction begins. A method that joins a transaction in progress runs at that transaction's level.
- `SERIALIZABLE` transactions can be aborted by the database when they conflict, and should be retried by the caller.
- A level SQLAlchemy does not support for your database (`-` above) raises SQLAlchemy's `ArgumentError` when the transaction begins. PostgreSQL has no real `READ_UNCOMMITTED`: it runs it as `READ_COMMITTED`, so SQLAlchemy rejects it. Use `READ_COMMITTED` instead.

## Programmatic Transactions

`transaction()` is the context-manager form of `@Transactional`, with the same options. Use it to wrap part of a method, or code outside a component:

```python
from mitsuki import Propagation, transaction

async def rebalance(self):
    report = await self.build_report()  # outside the transaction

    async with transaction():
        for account in report.accounts:
            await self.accounts.save(account)

    async with transaction(propagation=Propagation.REQUIRES_NEW):
        await self.audit.save(AuditLog(message="rebalanced"))
```

## Class-Level and Repository Usage

`@Transactional` on a class makes every public async method it defines or inherits transactional. A method with its own `@Transactional` keeps its own settings, and sync methods are left as they are:

```python
@Transactional()
@Service()
class AccountService:
    async def open(self, owner: str): ...    # transactional

    @Transactional(propagation=Propagation.REQUIRES_NEW)
    async def audit(self, message: str): ... # REQUIRES_NEW

    def describe(self) -> str: ...           # not transactional
```

On a `@CrudRepository`, class-level `@Transactional` also covers the built-in methods (`save`, `find_all`, ...). `@Transactional` on a single Query DSL or `@Query` method is kept on the method Mitsuki generates for it:

```python
@CrudRepository(entity=AuditLog)
class AuditRepository:
    @Transactional(propagation=Propagation.REQUIRES_NEW)
    async def delete_by_level(self, level: str) -> None: ...
```

The order of `@Transactional` relative to `@Service`, `@CrudRepository`, `@Query`, `@Modifying` and `@Instrumented` does not matter.

## Custom Queries Inside a Transaction

Inside a transaction, `get_connection()` yields the transaction's connection and leaves it open on exit, so SQLAlchemy Core queries take part in the transaction:

```python
@CrudRepository(entity=Account)
class AccountRepository:
    async def debit_all(self, amount: int):
        table = self.adapter.get_table(Account)
        async with self.get_connection() as conn:
            await conn.execute(update(table).values(balance=table.c.balance - amount))
```

Do not call `conn.commit()` or `conn.rollback()` on this connection: that ends the transaction that `@Transactional` manages. Outside a transaction, `get_connection()` behaves as before and returns a new connection that is closed on exit.

## Limitations

- **Async methods only.** `@Transactional` on a sync method raises `TypeError` when the class is defined.
- **One connection per transaction.** A transaction holds a pooled connection, and the database may hold locks, until it ends. Avoid slow work such as HTTP calls inside transactional methods: enough slow transactions running at once can exhaust the pool (`database.pool.size`).
- **No concurrent database calls inside a transaction.** A connection runs one statement at a time. Repository calls made through `asyncio.gather` or `asyncio.create_task` inside a transaction raise `TransactionException`. Await them one after another instead. A `@Transactional` method run in a spawned task begins its own, independent transaction.
- **SQLite.** An in-memory database (`sqlite:///:memory:`) has a single shared connection, so `REQUIRES_NEW` raises `TransactionException` there. File-based SQLite allows a single writer at a time: a `REQUIRES_NEW` transaction that writes after its outer transaction has written fails with `database is locked`.

## Coming From Spring

| Spring | Mitsuki |
|---|---|
| `@Transactional` | `@Transactional()` |
| `TransactionTemplate` | `async with transaction():` |
| `propagation = Propagation.REQUIRED / REQUIRES_NEW / NESTED` | `propagation=Propagation.REQUIRED / REQUIRES_NEW / NESTED` |
| `SUPPORTS`, `MANDATORY`, `NOT_SUPPORTED`, `NEVER` | Not supported |
| Rolls back on unchecked exceptions only | Rolls back on every exception |
| `noRollbackFor` | `no_rollback_for` |
| `rollbackFor` | Not needed: every exception already rolls back |
| `isolation = Isolation.SERIALIZABLE` | `isolation=Isolation.SERIALIZABLE` |
| `readOnly`, `timeout` | Not supported |
| `UnexpectedRollbackException` | `UnexpectedRollbackException` |
| Self-invocation (`this.method()`) bypasses the proxy | `self.method()` is transactional: the method itself is wrapped, not the object |
| Transaction bound to the thread | Transaction bound to the asyncio task |
