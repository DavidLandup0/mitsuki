"""
Transaction demarcation for repository calls.

The active transaction is bound to the task that began it through a
ContextVar, so every repository call awaited inside a transactional block runs
on the transaction's connection.
"""

import asyncio
import functools
import inspect
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from types import FunctionType
from typing import AsyncIterator, Callable, Optional, Tuple, Type

from sqlalchemy.ext.asyncio import AsyncConnection

from mitsuki.core.enums import Isolation, Propagation
from mitsuki.data.adapters.base import get_database_adapter
from mitsuki.exceptions import TransactionException, UnexpectedRollbackException

# Set on transactional methods and classes to the settings of their
# @Transactional, so @CrudRepository can carry them onto generated methods.
MARKER = "__mitsuki_transactional__"


@dataclass
class _TransactionState:
    connection: AsyncConnection
    owner: asyncio.Task
    rollback_only: bool = False
    closed: bool = False


_current: ContextVar[Optional[_TransactionState]] = ContextVar(
    "mitsuki_transaction", default=None
)


def _open_state() -> Optional[_TransactionState]:
    """The transaction in progress in this context, begun by any task."""
    state = _current.get()
    if state is None or state.closed:
        return None
    return state


def current_connection() -> Optional[AsyncConnection]:
    """
    The connection of the transaction in progress, or None outside one.

    Tasks spawned inside a transaction inherit it, but a connection runs one
    statement at a time, so only the task that began the transaction may use it.
    """
    state = _open_state()
    if state is None:
        return None
    if state.owner is not asyncio.current_task():
        raise TransactionException(
            "A transaction's connection cannot be used from a task spawned "
            "inside it. Await database calls directly instead of through "
            "asyncio.gather or asyncio.create_task."
        )
    return state.connection


def _rolls_back(error: BaseException, no_rollback_for: Tuple[Type, ...]) -> bool:
    return not isinstance(error, no_rollback_for)


@asynccontextmanager
async def transaction(
    propagation: Propagation = Propagation.REQUIRED,
    isolation: Optional[Isolation] = None,
    no_rollback_for: Tuple[Type[BaseException], ...] = (),
) -> AsyncIterator[None]:
    """
    Run a block in a transaction.

    A normal exit commits. An exception rolls back, unless it is an instance of
    a type in no_rollback_for, and is re-raised either way.

        async with transaction():
            await accounts.save(debited)
            await accounts.save(credited)

    Args:
        propagation: REQUIRED joins the transaction in progress or begins one.
            REQUIRES_NEW suspends it and begins one on a separate connection.
            NESTED rolls back to a savepoint inside it, or begins one.
        isolation: Isolation level, applied only where a transaction begins
        no_rollback_for: Exception types that commit instead of rolling back
    """
    state = _open_state()
    owned = state is not None and state.owner is asyncio.current_task()

    if owned and propagation == Propagation.REQUIRED:
        context = _join(state, no_rollback_for)
    elif owned and propagation == Propagation.NESTED:
        context = _savepoint(state, no_rollback_for)
    else:
        context = _begin(isolation, no_rollback_for, suspending=state is not None)

    async with context:
        yield


@asynccontextmanager
async def _join(
    state: _TransactionState, no_rollback_for: Tuple[Type, ...]
) -> AsyncIterator[None]:
    try:
        yield
    except BaseException as error:
        if _rolls_back(error, no_rollback_for):
            state.rollback_only = True
        raise


@asynccontextmanager
async def _savepoint(
    state: _TransactionState, no_rollback_for: Tuple[Type, ...]
) -> AsyncIterator[None]:
    savepoint = await state.connection.begin_nested()
    try:
        yield
    except BaseException as error:
        if _rolls_back(error, no_rollback_for):
            await savepoint.rollback()
        else:
            await savepoint.commit()
        raise
    await savepoint.commit()


@asynccontextmanager
async def _begin(
    isolation: Optional[Isolation],
    no_rollback_for: Tuple[Type, ...],
    suspending: bool,
) -> AsyncIterator[None]:
    adapter = get_database_adapter()
    if suspending and not adapter.supports_concurrent_transactions:
        raise TransactionException(
            "Cannot begin a transaction while another is in progress: this "
            "database has a single shared connection (SQLite :memory:)."
        )

    connection = await adapter.open_connection()
    try:
        if isolation is not None:
            await connection.execution_options(isolation_level=isolation.value)
        await connection.begin()
        state = _TransactionState(connection, asyncio.current_task())
        token = _current.set(state)
        try:
            yield
        except BaseException as error:
            if state.rollback_only or _rolls_back(error, no_rollback_for):
                await connection.rollback()
            else:
                await connection.commit()
            raise
        finally:
            state.closed = True
            _current.reset(token)

        if state.rollback_only:
            await connection.rollback()
            raise UnexpectedRollbackException(
                "Transaction rolled back: a block that joined it failed, and "
                "the failure was caught before the transaction completed."
            )
        await connection.commit()
    finally:
        await connection.close()


def _is_async(func: Callable) -> bool:
    return inspect.iscoroutinefunction(inspect.unwrap(func))


def _wrap_function(func: Callable, settings: tuple) -> Callable:
    if not _is_async(func):
        raise TypeError(
            f"@Transactional requires an async method, but "
            f"'{func.__qualname__}' is synchronous"
        )

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        async with transaction(*settings):
            return await func(*args, **kwargs)

    setattr(wrapper, MARKER, settings)
    return wrapper


def _wrap_class(cls: Type, settings: tuple) -> Type:
    """
    Wrap the public async methods a class defines or inherits. Methods with
    their own @Transactional keep their settings, and sync methods are left
    as they are.
    """
    setattr(cls, MARKER, settings)
    seen = set()

    for klass in cls.__mro__:
        if klass is object:
            continue

        for name, attr in list(vars(klass).items()):
            if name.startswith("_") or name in seen:
                continue

            seen.add(name)

            if (
                isinstance(attr, FunctionType)
                and MARKER not in attr.__dict__
                and _is_async(attr)
            ):
                setattr(cls, name, _wrap_function(attr, settings))

    return cls


def Transactional(
    propagation: Propagation = Propagation.REQUIRED,
    isolation: Optional[Isolation] = None,
    no_rollback_for: Tuple[Type[BaseException], ...] = (),
):
    """
    Run a method, or every public async method of a class, in a transaction.

    See transaction() for the meaning of each setting. Only async methods can
    be transactional.

        @Service()
        class TransferService:
            @Transactional()
            async def transfer(self, source: int, target: int, amount: int):
                ...
    """
    settings = (propagation, isolation, tuple(no_rollback_for))

    def decorator(target):
        if inspect.isclass(target):
            return _wrap_class(target, settings)
        return _wrap_function(target, settings)

    return decorator
