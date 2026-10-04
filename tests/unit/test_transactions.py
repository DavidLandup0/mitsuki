"""
Tests for @Transactional and transaction().
"""

import asyncio
from dataclasses import dataclass
from typing import List

import pytest
import pytest_asyncio
from sqlalchemy import insert
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import QueuePool
from testcontainers.community.mysql import MySqlContainer
from testcontainers.community.postgres import PostgresContainer

import mitsuki.core.decorators as decorators
from mitsuki import Isolation, Propagation, Transactional, transaction
from mitsuki.core.decorators import Service
from mitsuki.core.enums import DatabaseDialect
from mitsuki.core.instrumentation import (
    InstrumentationRegistry,
    Instrumented,
    apply_instrumentation,
)
from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.data import (
    CrudRepository,
    Entity,
    Id,
    Modifying,
    Query,
    SQLAlchemyAdapter,
    get_entity_metadata,
    set_database_adapter,
)
from mitsuki.exceptions import TransactionException, UnexpectedRollbackException


class Boom(Exception):
    pass


class Declined(Exception):
    pass


class HardDeclined(Declined):
    pass


@Entity()
@dataclass
class Wallet:
    id: int = Id()
    owner: str = ""
    balance: int = 0


@Entity()
@dataclass
class AuditLog:
    id: int = Id()
    message: str = ""


@CrudRepository(entity=Wallet)
class WalletRepository:
    async def find_by_owner(self, owner: str) -> List[Wallet]: ...

    async def delete_by_owner(self, owner: str) -> None: ...

    @Modifying
    @Query("UPDATE Wallet w SET w.balance = :balance WHERE w.owner = :owner")
    async def set_balance(self, owner: str, balance: int) -> int: ...

    async def insert_raw(self, owner: str) -> None:
        table = self.adapter.get_table(Wallet)
        async with self.get_connection() as conn:
            await conn.execute(insert(table).values(owner=owner, balance=0))

    async def isolation_level(self) -> str:
        async with self.get_connection() as conn:
            return await conn.get_isolation_level()


@CrudRepository(entity=AuditLog)
class AuditRepository:
    pass


@Service()
class AuditService:
    def __init__(self, audit: AuditRepository):
        self.audit = audit

    @Transactional(propagation=Propagation.REQUIRES_NEW)
    async def record(self, message: str):
        await self.audit.save(AuditLog(message=message))

    @Transactional(propagation=Propagation.REQUIRES_NEW)
    async def record_then_fail(self, message: str):
        await self.audit.save(AuditLog(message=message))
        raise Boom()

    @Transactional()
    async def record_joined(self, message: str):
        await self.audit.save(AuditLog(message=message))


@Service()
class WalletService:
    def __init__(self, wallets: WalletRepository, audit: AuditService):
        self.wallets = wallets
        self.audit = audit

    @Transactional()
    async def open(self, owner: str):
        await self.wallets.save(Wallet(owner=owner))

    @Transactional()
    async def open_then_fail(self, owner: str):
        await self.wallets.save(Wallet(owner=owner))
        raise Boom()

    @Transactional(no_rollback_for=(Declined,))
    async def open_then_decline(self, owner: str, error: Exception):
        await self.wallets.save(Wallet(owner=owner))
        raise error

    @Transactional()
    async def open_then_hang(self, owner: str, started: asyncio.Event):
        await self.wallets.save(Wallet(owner=owner))
        started.set()
        await asyncio.Event().wait()

    @Transactional()
    async def open_two(self, first: str, second: str):
        await self.open(first)
        await self.open_then_fail(second)

    @Transactional()
    async def open_and_swallow_inner_failure(self, first: str, second: str):
        await self.open(first)
        try:
            await self.open_then_fail(second)
        except Boom:
            pass

    @Transactional()
    async def open_and_swallow_declined_inner(self, first: str, second: str):
        await self.open(first)
        try:
            await self.open_then_decline(second, Declined())
        except Declined:
            pass

    @Transactional()
    async def connections_seen(self):
        async with self.wallets.get_connection() as outer:
            inner = await self._connection_in_joined_call()
        return outer, inner

    @Transactional()
    async def _connection_in_joined_call(self):
        async with self.wallets.get_connection() as conn:
            return conn

    @Transactional()
    async def audit_then_fail(self, owner: str, message: str):
        await self.audit.record(message)
        await self.wallets.save(Wallet(owner=owner))
        raise Boom()

    @Transactional()
    async def open_after_failed_audit(self, owner: str, message: str):
        try:
            await self.audit.record_then_fail(message)
        except Boom:
            pass
        await self.wallets.save(Wallet(owner=owner))

    @Transactional()
    async def open_with_requires_new_audit(self, owner: str, message: str):
        await self.wallets.save(Wallet(owner=owner))
        await self.audit.record(message)

    @Transactional(propagation=Propagation.NESTED)
    async def nested_open_then_fail(self, owner: str):
        await self.wallets.save(Wallet(owner=owner))
        raise Boom()

    @Transactional(propagation=Propagation.NESTED)
    async def nested_open(self, owner: str):
        await self.wallets.save(Wallet(owner=owner))

    @Transactional()
    async def open_and_swallow_nested_failure(self, first: str, second: str):
        await self.open(first)
        try:
            await self.nested_open_then_fail(second)
        except Boom:
            pass

    @Transactional(propagation=Propagation.NESTED)
    async def nested_open_through_joined_failure(self, owner: str):
        await self.open_then_fail(owner)

    @Transactional()
    async def open_and_swallow_nested_joined_failure(self, first: str, second: str):
        await self.open(first)
        try:
            await self.nested_open_through_joined_failure(second)
        except Boom:
            pass

    @Transactional()
    async def nested_open_then_outer_fail(self, owner: str):
        await self.nested_open(owner)
        raise Boom()

    @Transactional(isolation=Isolation.SERIALIZABLE)
    async def isolation_level(self) -> str:
        return await self.wallets.isolation_level()

    @Transactional()
    async def mixed_writes_then_fail(self, owner: str):
        await self.wallets.save(Wallet(owner=owner))
        await self.wallets.set_balance(owner, 100)
        await self.wallets.insert_raw(f"{owner}-raw")
        raise Boom()

    @Transactional()
    async def delete_then_fail(self, owner: str):
        await self.wallets.delete_by_owner(owner)
        raise Boom()

    @Transactional()
    async def concurrent_reads(self):
        return await asyncio.gather(self.wallets.count(), self.wallets.count())

    @Transactional()
    async def open_audit_then_fail(self, owner: str, message: str):
        await self.wallets.save(Wallet(owner=owner))
        await self.audit.record(message)
        raise Boom()

    @Transactional()
    async def spawn_audit_then_fail(self, owner: str, message: str):
        await asyncio.create_task(self.audit.record_joined(message))
        await self.wallets.save(Wallet(owner=owner))
        raise Boom()


@pytest.fixture(scope="session")
def postgresql_url():
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def mysql_url():
    with MySqlContainer("mysql:8.4", dialect="aiomysql") as mysql:
        yield mysql.get_connection_url()


async def _connect(url: str) -> SQLAlchemyAdapter:
    adapter = SQLAlchemyAdapter()
    await adapter.connect(url)
    for entity in (Wallet, AuditLog):
        await adapter.create_table_if_not_exists(get_entity_metadata(entity))
    set_database_adapter(adapter)
    return adapter


async def _disconnect(adapter: SQLAlchemyAdapter):
    async with adapter.engine.begin() as conn:
        await conn.run_sync(adapter.metadata.drop_all)
    await adapter.disconnect()
    set_database_adapter(None)


@pytest_asyncio.fixture(
    params=[
        DatabaseDialect.SQLITE,
        DatabaseDialect.POSTGRESQL,
        DatabaseDialect.MYSQL,
    ]
)
async def database(request, tmp_path):
    """Every backend: file-based SQLite, PostgreSQL and MySQL."""
    if request.param == DatabaseDialect.SQLITE:
        url = f"sqlite+aiosqlite:///{tmp_path / 'transactions.db'}"
    else:
        url = request.getfixturevalue(f"{request.param.value}_url")
    adapter = await _connect(url)
    yield adapter
    await _disconnect(adapter)


@pytest_asyncio.fixture
async def memory_db():
    adapter = await _connect("sqlite+aiosqlite:///:memory:")
    yield adapter
    await _disconnect(adapter)


def dialect(adapter: SQLAlchemyAdapter) -> DatabaseDialect:
    return DatabaseDialect.from_string(adapter.engine.dialect.name)


@pytest.fixture
def wallets():
    return WalletRepository()


@pytest.fixture
def audit():
    return AuditRepository()


@pytest.fixture
def service(wallets, audit):
    return WalletService(wallets, AuditService(audit))


async def owners(wallets: WalletRepository) -> List[str]:
    return sorted(wallet.owner for wallet in await wallets.find_all())


async def messages(audit: AuditRepository) -> List[str]:
    return sorted(entry.message for entry in await audit.find_all())


class TestCommitAndRollback:
    @pytest.mark.asyncio
    async def test_commits_on_return(self, database, service, wallets):
        await service.open("alice")

        assert await owners(wallets) == ["alice"]

    @pytest.mark.asyncio
    async def test_rolls_back_on_exception(self, database, service, wallets):
        with pytest.raises(Boom):
            await service.open_then_fail("alice")

        assert await owners(wallets) == []

    @pytest.mark.asyncio
    async def test_rolls_back_on_cancellation(self, database, service, wallets):
        started = asyncio.Event()
        task = asyncio.create_task(service.open_then_hang("alice", started))
        waiter = asyncio.create_task(started.wait())
        await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
        waiter.cancel()
        assert not task.done(), task.exception()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert await owners(wallets) == []

    @pytest.mark.asyncio
    async def test_no_rollback_for_commits_and_reraises(
        self, database, service, wallets
    ):
        with pytest.raises(Declined):
            await service.open_then_decline("alice", Declined())

        assert await owners(wallets) == ["alice"]

    @pytest.mark.asyncio
    async def test_no_rollback_for_covers_subclasses(self, database, service, wallets):
        with pytest.raises(HardDeclined):
            await service.open_then_decline("alice", HardDeclined())

        assert await owners(wallets) == ["alice"]

    @pytest.mark.asyncio
    async def test_other_exceptions_still_roll_back(self, database, service, wallets):
        with pytest.raises(Boom):
            await service.open_then_decline("alice", Boom())

        assert await owners(wallets) == []


class TestRequired:
    @pytest.mark.asyncio
    async def test_joined_calls_share_one_connection(self, database, service):
        outer, inner = await service.connections_seen()

        assert outer is inner

    @pytest.mark.asyncio
    async def test_outer_rollback_undoes_joined_writes(
        self, database, service, wallets
    ):
        with pytest.raises(Boom):
            await service.open_two("alice", "bob")

        assert await owners(wallets) == []

    @pytest.mark.asyncio
    async def test_swallowed_joined_failure_raises_unexpected_rollback(
        self, database, service, wallets
    ):
        with pytest.raises(UnexpectedRollbackException):
            await service.open_and_swallow_inner_failure("alice", "bob")

        assert await owners(wallets) == []

    @pytest.mark.asyncio
    async def test_swallowed_no_rollback_for_failure_commits(
        self, database, service, wallets
    ):
        await service.open_and_swallow_declined_inner("alice", "bob")

        assert await owners(wallets) == ["alice", "bob"]


class TestRequiresNew:
    @pytest.mark.asyncio
    async def test_inner_commit_survives_outer_rollback(
        self, database, service, wallets, audit
    ):
        with pytest.raises(Boom):
            await service.audit_then_fail("alice", "opened alice")

        assert await owners(wallets) == []
        assert await messages(audit) == ["opened alice"]

    @pytest.mark.asyncio
    async def test_inner_rollback_leaves_outer_intact(
        self, database, service, wallets, audit
    ):
        await service.open_after_failed_audit("alice", "opened alice")

        assert await owners(wallets) == ["alice"]
        assert await messages(audit) == []

    @pytest.mark.asyncio
    async def test_inner_commits_after_outer_has_written(
        self, database, service, wallets, audit
    ):
        if dialect(database) == DatabaseDialect.SQLITE:
            pytest.skip("SQLite allows one writer: the outer write locks the file")

        with pytest.raises(Boom):
            await service.open_audit_then_fail("alice", "opened alice")

        assert await owners(wallets) == []
        assert await messages(audit) == ["opened alice"]

    @pytest.mark.asyncio
    async def test_unsupported_on_single_connection_database(
        self, memory_db, service, wallets
    ):
        with pytest.raises(TransactionException):
            await service.open_with_requires_new_audit("alice", "opened alice")

        assert await owners(wallets) == []


class TestNested:
    @pytest.mark.asyncio
    async def test_savepoint_rollback_keeps_outer_work(
        self, database, service, wallets
    ):
        await service.open_and_swallow_nested_failure("alice", "bob")

        assert await owners(wallets) == ["alice"]

    @pytest.mark.asyncio
    async def test_savepoint_contains_a_failed_joined_block(
        self, database, service, wallets
    ):
        await service.open_and_swallow_nested_joined_failure("alice", "bob")

        assert await owners(wallets) == ["alice"]

    @pytest.mark.asyncio
    async def test_outer_rollback_undoes_released_savepoint(
        self, database, service, wallets
    ):
        with pytest.raises(Boom):
            await service.nested_open_then_outer_fail("alice")

        assert await owners(wallets) == []

    @pytest.mark.asyncio
    async def test_begins_a_transaction_when_none_is_active(
        self, database, service, wallets
    ):
        await service.nested_open("alice")
        with pytest.raises(Boom):
            await service.nested_open_then_fail("bob")

        assert await owners(wallets) == ["alice"]


# Levels SQLAlchemy's dialects reject. PostgreSQL runs READ UNCOMMITTED as
# READ COMMITTED, so SQLAlchemy does not offer it.
UNSUPPORTED_ISOLATION = {
    (DatabaseDialect.SQLITE, Isolation.READ_COMMITTED),
    (DatabaseDialect.SQLITE, Isolation.REPEATABLE_READ),
    (DatabaseDialect.POSTGRESQL, Isolation.READ_UNCOMMITTED),
}


class TestIsolation:
    @pytest.mark.asyncio
    async def test_isolation_level_reaches_the_connection(self, database, service):
        assert await service.isolation_level() == Isolation.SERIALIZABLE

    @pytest.mark.parametrize("isolation", list(Isolation))
    @pytest.mark.asyncio
    async def test_every_level_reaches_the_connection_or_is_rejected(
        self, database, wallets, isolation
    ):
        if (dialect(database), isolation) not in UNSUPPORTED_ISOLATION:
            async with transaction(isolation=isolation):
                assert await wallets.isolation_level() == isolation
            return

        with pytest.raises(ArgumentError):
            async with transaction(isolation=isolation):
                pass

        if isinstance(database.engine.pool, QueuePool):
            assert database.engine.pool.checkedout() == 0
        assert await wallets.count() == 0

    @pytest.mark.asyncio
    async def test_joined_block_runs_at_the_outer_level(self, database, wallets):
        async with transaction(isolation=Isolation.SERIALIZABLE):
            async with transaction(isolation=Isolation.READ_UNCOMMITTED):
                assert await wallets.isolation_level() == Isolation.SERIALIZABLE


class TestRepositoryParticipation:
    @pytest.mark.asyncio
    async def test_save_query_modifying_and_connection_writes_roll_back(
        self, database, service, wallets
    ):
        with pytest.raises(Boom):
            await service.mixed_writes_then_fail("alice")

        assert await owners(wallets) == []

    @pytest.mark.asyncio
    async def test_query_dsl_delete_rolls_back(self, database, service, wallets):
        await wallets.save(Wallet(owner="alice"))

        with pytest.raises(Boom):
            await service.delete_then_fail("alice")

        assert await owners(wallets) == ["alice"]

    @pytest.mark.asyncio
    async def test_repository_calls_outside_a_transaction_commit_individually(
        self, database, wallets
    ):
        await wallets.save(Wallet(owner="alice"))
        await wallets.set_balance("alice", 100)

        assert [wallet.balance for wallet in await wallets.find_all()] == [100]


@pytest.fixture
def isolated_components(isolated_container):
    saved = list(decorators._instrumentable_components)
    decorators._instrumentable_components.clear()
    try:
        yield
    finally:
        decorators._instrumentable_components[:] = saved


@pytest.mark.usefixtures("isolated_components")
class TestDecoratorPlacement:
    @pytest.mark.asyncio
    async def test_query_dsl_stub_keeps_its_propagation(self, database, wallets):
        @CrudRepository(entity=Wallet)
        class Wallets:
            @Transactional(propagation=Propagation.REQUIRES_NEW)
            async def delete_by_owner(self, owner: str) -> None: ...

        await wallets.save(Wallet(owner="alice"))

        with pytest.raises(Boom):
            async with transaction():
                await Wallets().delete_by_owner("alice")
                raise Boom()

        assert await owners(wallets) == []

    @pytest.mark.asyncio
    async def test_transactional_above_query_keeps_its_propagation(
        self, database, wallets
    ):
        @CrudRepository(entity=Wallet)
        class Wallets:
            @Transactional(propagation=Propagation.REQUIRES_NEW)
            @Modifying
            @Query("UPDATE Wallet w SET w.balance = :balance WHERE w.owner = :owner")
            async def set_balance(self, owner: str, balance: int) -> int: ...

        await wallets.save(Wallet(owner="alice"))

        with pytest.raises(Boom):
            async with transaction():
                await Wallets().set_balance("alice", 100)
                raise Boom()

        assert [wallet.balance for wallet in await wallets.find_all()] == [100]

    @pytest.mark.asyncio
    async def test_transactional_below_query_keeps_its_propagation(
        self, database, wallets
    ):
        @CrudRepository(entity=Wallet)
        class Wallets:
            @Modifying
            @Query("UPDATE Wallet w SET w.balance = :balance WHERE w.owner = :owner")
            @Transactional(propagation=Propagation.REQUIRES_NEW)
            async def set_balance(self, owner: str, balance: int) -> int: ...

        await wallets.save(Wallet(owner="alice"))

        with pytest.raises(Boom):
            async with transaction():
                await Wallets().set_balance("alice", 100)
                raise Boom()

        assert [wallet.balance for wallet in await wallets.find_all()] == [100]

    @pytest.mark.asyncio
    async def test_class_level_above_crud_repository(self, database, wallets):
        @Transactional(propagation=Propagation.REQUIRES_NEW)
        @CrudRepository(entity=Wallet)
        class Wallets:
            pass

        with pytest.raises(Boom):
            async with transaction():
                await Wallets().save(Wallet(owner="alice"))
                raise Boom()

        assert await owners(wallets) == ["alice"]

    @pytest.mark.asyncio
    async def test_class_level_below_crud_repository(self, database, wallets):
        @CrudRepository(entity=Wallet)
        @Transactional(propagation=Propagation.REQUIRES_NEW)
        class Wallets:
            async def delete_by_owner(self, owner: str) -> None: ...

        await wallets.save(Wallet(owner="alice"))

        with pytest.raises(Boom):
            async with transaction():
                await Wallets().save(Wallet(owner="bob"))
                await Wallets().delete_by_owner("alice")
                raise Boom()

        assert await owners(wallets) == ["bob"]

    @pytest.mark.parametrize("transactional_first", [True, False])
    @pytest.mark.asyncio
    async def test_class_level_on_service(self, database, wallets, transactional_first):
        class Openings:
            def __init__(self, wallets: WalletRepository):
                self.wallets = wallets

            async def open_then_fail(self, owner: str):
                await self.wallets.save(Wallet(owner=owner))
                raise Boom()

            def describe(self) -> str:
                return "openings"

        if transactional_first:
            Openings = Transactional()(Service()(Openings))
        else:
            Openings = Service()(Transactional()(Openings))
        openings = Openings(wallets)

        with pytest.raises(Boom):
            await openings.open_then_fail("alice")

        assert await owners(wallets) == []
        assert openings.describe() == "openings"

    @pytest.mark.asyncio
    async def test_class_level_covers_inherited_methods(self, database, wallets):
        class Base:
            def __init__(self, wallets: WalletRepository):
                self.wallets = wallets

            async def open_then_fail(self, owner: str):
                await self.wallets.save(Wallet(owner=owner))
                raise Boom()

        @Transactional()
        @Service()
        class Openings(Base):
            pass

        with pytest.raises(Boom):
            await Openings(wallets).open_then_fail("alice")

        assert await owners(wallets) == []

    @pytest.mark.asyncio
    async def test_method_level_overrides_class_level(self, database, wallets):
        @Transactional(propagation=Propagation.REQUIRES_NEW)
        @Service()
        class Openings:
            def __init__(self, wallets: WalletRepository):
                self.wallets = wallets

            @Transactional()
            async def open(self, owner: str):
                await self.wallets.save(Wallet(owner=owner))

        with pytest.raises(Boom):
            async with transaction():
                await Openings(wallets).open("alice")
                raise Boom()

        assert await owners(wallets) == []

    def test_sync_method_is_rejected(self):
        with pytest.raises(TypeError):

            @Transactional()
            def open(self, owner: str):
                pass

    @pytest.mark.asyncio
    async def test_composes_with_instrumentation(self, database, wallets):
        @Instrumented()
        @Service()
        class Openings:
            def __init__(self, wallets: WalletRepository):
                self.wallets = wallets

            @Transactional()
            async def open_then_fail(self, owner: str):
                await self.wallets.save(Wallet(owner=owner))
                raise Boom()

        registry = InstrumentationRegistry(MetricsStorage())
        registry.enable()
        apply_instrumentation(object, registry)

        with pytest.raises(Boom):
            await Openings(wallets).open_then_fail("alice")

        assert await owners(wallets) == []
        failures = registry._core.counter("component_calls_total").get(
            {"component": "Openings", "method": "open_then_fail", "status": "failure"}
        )
        assert failures == 1.0


class TestProgrammatic:
    @pytest.mark.asyncio
    async def test_commits_on_exit(self, database, wallets):
        async with transaction():
            await wallets.save(Wallet(owner="alice"))

        assert await owners(wallets) == ["alice"]

    @pytest.mark.asyncio
    async def test_rolls_back_on_exception(self, database, wallets):
        with pytest.raises(Boom):
            async with transaction():
                await wallets.save(Wallet(owner="alice"))
                raise Boom()

        assert await owners(wallets) == []

    @pytest.mark.asyncio
    async def test_nested_block_rolls_back_to_its_savepoint(self, database, wallets):
        async with transaction():
            await wallets.save(Wallet(owner="alice"))
            with pytest.raises(Boom):
                async with transaction(propagation=Propagation.NESTED):
                    await wallets.save(Wallet(owner="bob"))
                    raise Boom()

        assert await owners(wallets) == ["alice"]

    @pytest.mark.asyncio
    async def test_no_rollback_for(self, database, wallets):
        with pytest.raises(Declined):
            async with transaction(no_rollback_for=(Declined,)):
                await wallets.save(Wallet(owner="alice"))
                raise Declined()

        assert await owners(wallets) == ["alice"]


class TestConcurrentTransactions:
    @pytest.mark.asyncio
    async def test_concurrent_transactions_are_independent(
        self, database, service, wallets
    ):
        results = await asyncio.gather(
            service.open_two("alice", "bob"),
            service.open("carol"),
            return_exceptions=True,
        )

        assert isinstance(results[0], Boom)
        assert await owners(wallets) == ["carol"]


class TestTaskBoundary:
    @pytest.mark.asyncio
    async def test_concurrent_tasks_cannot_use_the_connection(self, database, service):
        with pytest.raises(TransactionException):
            await service.concurrent_reads()

    @pytest.mark.asyncio
    async def test_spawned_task_begins_its_own_transaction(
        self, database, service, wallets, audit
    ):
        with pytest.raises(Boom):
            await service.spawn_audit_then_fail("alice", "opened alice")

        assert await owners(wallets) == []
        assert await messages(audit) == ["opened alice"]
