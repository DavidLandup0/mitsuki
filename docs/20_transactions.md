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

## Overview

Without transactional support, every repository call commits on its own. 
In the method below, if the second `save()` fails, the first one has already been committed and money disappears:

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

Mitsuki decides where transactions begin and end. The transactions themselves - atomicity, locking, isolation and savepoints - are provided by your database, through SQLAlchemy.

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

- A return commits.
- Any exception rolls back and is re-raised. This includes `asyncio.CancelledError`, so a cancelled request never commits.
- Repository methods need no changes: built-in methods, Query DSL methods, `@Query` methods and `get_connection()` all join the transaction in progress.

The transaction follows the call chain. A repository called from a helper called from the transactional method still runs inside the transaction.

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

When a joined method fails, the shared transaction is marked rollback-only. If the outer method catches that exception and returns normally, the transaction is still rolled back and `UnexpectedRollbackException` is raised still:

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

Suspend the transaction in progress and run in a new, independent one on a separate connection. The new transaction commits or rolls back on its own, regardless of the outer one. This is useful for example for audit logs that must persist even when the operation they record fails:

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

Run inside the transaction in progress, behind a savepoint. If the nested method fails, only its own work is rolled back and the outer transaction continues. If the outer transaction later rolls back, the nested work is rolled back with it. With no transaction in progress, `NESTED` begins one, like `REQUIRED`:

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

Every exception rolls back by default. If you wish to specify exceptions that should commit the work done so far, you can do so in `no_rollback_for`. Subclasses of the listed types match too. 

The exception is re-raised either way:

```python
@Transactional(no_rollback_for=(PaymentDeclined,))
async def checkout(self, cart: Cart):
    order = await self.orders.save(Order.from_cart(cart, status="pending"))
    await self.payments.charge(order)  # PaymentDeclined: the pending order is kept
```

A joined method that fails with an exception from its own `no_rollback_for` does not mark the shared transaction rollback-only.

## Isolation Levels

While your transaction runs, other requests can run their own transactions on the same tables. 
Isolation decides what your queries return for rows those other transactions are changing at the same time, and how transactions that run concurrently interact with each other's in-flight results:

```python
from mitsuki import Isolation, Transactional

@Transactional(isolation=Isolation.SERIALIZABLE)
async def withdraw(self, account_id: int, amount: int):
    ...
```

### What each level sees

Take two requests running at once. Account 1 holds a balance of `100`. Request A sets it to `50`, while request B reads it twice in its own transaction:

```
time   Request A                          Request B
 t1    begin                              begin
 t2    save(balance=50)  (uncommitted)
 t3                                       find_by_id(1) → ?
 t4    commit
 t5                                       find_by_id(1) → ?
```

What B reads depends on B's isolation level:

| Level | Read at t3 | Read at t5 | What B sees |
|---|---|---|---|
| `READ_UNCOMMITTED` | `50` | `50` | A's uncommitted change ("dirty read"). Had A rolled back, B would have acted on a value that never got written. |
| `READ_COMMITTED` | `100` | `50` | Each query sees whatever is committed when it runs, so the same query can return different values within one transaction ("non-repeatable read"). |
| `REPEATABLE_READ` | `100` | `100` | A snapshot taken at B's first query. Changes committed after it stay invisible until B ends. |
| `SERIALIZABLE` | `100` | `100` | As `REPEATABLE_READ`, and the database aborts one of the transactions when they could not have run one after the other. On MySQL, B's read at t3 waits for A to commit instead. |

### When it matters: read, decide, write

Isolation matters for code that reads a value, decides on it and writes the result, such as a withdrawal:

```python
@Transactional()
async def withdraw(self, account_id: int, amount: int):
    account = await self.accounts.find_by_id(account_id)
    if account.balance < amount:
        raise InsufficientFunds()
    account.balance -= amount
    await self.accounts.save(account)
```

Two withdrawals of `80` from a balance of `100`, running at the same time, can both read `100` before either writes:

```
A: find_by_id → 100, 100 >= 80, save(balance=20), commit
B: find_by_id → 100, 100 >= 80, save(balance=20), commit    (B read before A committed)
```

Both withdrawals succeed and the balance ends at `20`. One withdrawal is lost. What each level does with this:

| Level | PostgreSQL | MySQL |
|---|---|---|
| `READ_COMMITTED` | Both commit; one update is lost | Both commit; one update is lost |
| `REPEATABLE_READ` | One is aborted with a serialization failure | Both commit; one update is lost |
| `SERIALIZABLE` | One is aborted with a serialization failure | One is aborted with a deadlock error |

An aborted transaction raises SQLAlchemy's `DBAPIError` (`OperationalError` on MySQL) and rolls back. Retry the whole method: the retry reads the new balance of `20` and raises `InsufficientFunds`.

The same pattern covers checking that a username is free, that stock remains, or that a time slot is open. Code that reads without acting on the result, or writes without reading first, is fine at the database's default level.

### Support by database

| Level | PostgreSQL | MySQL | SQLite |
|---|---|---|---|
| `READ_UNCOMMITTED` | - | Yes | Accepted, no effect |
| `READ_COMMITTED` | Default | Yes | - |
| `REPEATABLE_READ` | Yes | Default | - |
| `SERIALIZABLE` | Yes | Yes | Default |

- Isolation applies only where a transaction begins. A method that joins a transaction in progress runs at that transaction's level.
- A level SQLAlchemy does not support for your database (`-` above) raises SQLAlchemy's `ArgumentError` when the transaction begins. PostgreSQL has no real `READ_UNCOMMITTED`: it runs it as `READ_COMMITTED`, so SQLAlchemy rejects it. Use `READ_COMMITTED` instead.
- SQLite runs every transaction as `SERIALIZABLE`. It accepts `READ_UNCOMMITTED`, but the setting only applies between connections sharing a cache, which Mitsuki does not use, so transactions still never see each other's uncommitted changes.
- SQLite allows one writer at a time. In the withdrawal example, one transaction fails with SQLAlchemy's `OperationalError` (`database is locked`) and rolls back, so no update is lost.

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

Do not call `conn.commit()` or `conn.rollback()` on this connection: that ends the transaction that `@Transactional` manages. Outside a transaction, `get_connection()` returns a new connection that is closed on exit. Writes on it are discarded unless you commit them with `await conn.commit()` before the block ends.

## Limitations

- **Async methods only.** `@Transactional` on a sync method raises `TypeError` when the class is defined.
- **One connection per transaction.** A transaction holds a pooled connection, and the database may hold locks, until it ends. Avoid slow work such as HTTP calls inside transactional methods: enough slow transactions running at once can exhaust the pool (`database.pool.size`).
- **No concurrent database calls inside a transaction.** A connection runs one statement at a time. Repository calls made through `asyncio.gather` or `asyncio.create_task` inside a transaction raise `TransactionException`. Await them one after another instead. A `@Transactional` method run in a spawned task begins its own, independent transaction.
- **SQLite.** An in-memory database (`sqlite:///:memory:`) has a single shared connection, so `REQUIRES_NEW` raises `TransactionException` there. File-based SQLite allows a single writer at a time: a `REQUIRES_NEW` transaction that writes after its outer transaction has written fails with `database is locked`.