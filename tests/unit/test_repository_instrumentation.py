from dataclasses import dataclass
from typing import List
from unittest.mock import patch

import pytest
import pytest_asyncio

import mitsuki.core.decorators as decorators
from mitsuki import CrudRepository, Entity, Id, Query
from mitsuki.core.instrumentation import (
    InstrumentationRegistry,
    Instrumented,
    apply_instrumentation,
)
from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.data import SQLAlchemyAdapter, get_entity_metadata, set_database_adapter
from mitsuki.exceptions import QueryException


@Entity()
@dataclass
class LedgerEntry:
    id: int = Id()
    account: str = ""
    amount: int = 0


@pytest.fixture(autouse=True)
def _isolate(isolated_container):
    """A fresh container and an empty set of instrumentable components."""
    saved = list(decorators._instrumentable_components)
    decorators._instrumentable_components.clear()
    try:
        yield
    finally:
        decorators._instrumentable_components[:] = saved


@pytest_asyncio.fixture
async def database():
    adapter = SQLAlchemyAdapter()
    await adapter.connect("sqlite+aiosqlite:///:memory:")
    set_database_adapter(adapter)
    await adapter.create_table_if_not_exists(get_entity_metadata(LedgerEntry))

    yield adapter

    await adapter.disconnect()
    set_database_adapter(None)


class _App:
    """An application without application-wide instrumentation."""


def instrument(app_cls=_App) -> InstrumentationRegistry:
    registry = InstrumentationRegistry(MetricsStorage())
    registry.enable()
    apply_instrumentation(app_cls, registry)
    return registry


def calls(registry, method, status="success", component="LedgerRepository"):
    return registry._core.counter("component_calls_total").get(
        {"component": component, "method": method, "status": status}
    )


def ledger_repository():
    """Define a repository covering every kind of repository method."""

    @CrudRepository(entity=LedgerEntry)
    class LedgerRepository:
        async def find_by_account(self, account: str) -> List[LedgerEntry]: ...

        @Query("SELECT l FROM LedgerEntry l WHERE l.amount > :minimum")
        async def find_larger_than(self, minimum: int): ...

        async def balance(self, account: str) -> int:
            entries = await self.find_by_account(account)
            return sum(entry.amount for entry in entries)

        async def reject(self):
            raise ValueError("rejected")

    return LedgerRepository


@Instrumented()
class _InstrumentedApp:
    """An application with application-wide instrumentation."""


class TestCrudRepositoryInstrumentation:
    """Every kind of @CrudRepository method is recorded under the repository."""

    @pytest.mark.asyncio
    async def test_base_crud_methods_are_recorded(self, database):
        repository_cls = ledger_repository()
        registry = instrument(_InstrumentedApp)
        repository = repository_cls()

        await repository.save(LedgerEntry(account="ops", amount=5))
        await repository.find_all()
        await repository.count()

        assert calls(registry, "save") == 1.0
        assert calls(registry, "find_all") == 1.0
        assert calls(registry, "count") == 1.0

    @pytest.mark.asyncio
    async def test_query_dsl_method_is_recorded(self, database):
        repository_cls = ledger_repository()
        registry = instrument(_InstrumentedApp)
        repository = repository_cls()
        await repository.save(LedgerEntry(account="ops", amount=5))

        entries = await repository.find_by_account("ops")

        assert [entry.amount for entry in entries] == [5]
        assert calls(registry, "find_by_account") == 1.0

    @pytest.mark.asyncio
    async def test_custom_query_method_is_recorded(self, database):
        repository_cls = ledger_repository()
        registry = instrument(_InstrumentedApp)
        repository = repository_cls()
        await repository.save(LedgerEntry(account="ops", amount=5))

        await repository.find_larger_than(1)

        assert calls(registry, "find_larger_than") == 1.0

    @pytest.mark.asyncio
    async def test_implemented_method_is_recorded(self, database):
        repository_cls = ledger_repository()
        registry = instrument(_InstrumentedApp)
        repository = repository_cls()
        await repository.save(LedgerEntry(account="ops", amount=5))
        await repository.save(LedgerEntry(account="ops", amount=7))

        assert await repository.balance("ops") == 12
        assert calls(registry, "balance") == 1.0

    @pytest.mark.asyncio
    async def test_failing_method_is_recorded_as_failure(self, database):
        repository_cls = ledger_repository()
        registry = instrument(_InstrumentedApp)
        repository = repository_cls()

        with pytest.raises(ValueError, match="rejected"):
            await repository.reject()

        assert calls(registry, "reject", status="failure") == 1.0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("instrumented_outermost", [True, False])
    async def test_component_opt_in_is_independent_of_decorator_order(
        self, database, instrumented_outermost
    ):
        class Repo:
            async def find_by_account(self, account: str) -> List[LedgerEntry]: ...

        Repo.__name__ = Repo.__qualname__ = "LedgerRepository"

        if instrumented_outermost:
            repository_cls = Instrumented()(CrudRepository(entity=LedgerEntry)(Repo))
        else:
            repository_cls = CrudRepository(entity=LedgerEntry)(Instrumented()(Repo))

        registry = instrument()
        await repository_cls().find_by_account("ops")

        assert calls(registry, "find_by_account") == 1.0

    @pytest.mark.asyncio
    async def test_component_opt_out_wins_over_application(self, database):
        @Instrumented(enabled=False)
        @CrudRepository(entity=LedgerEntry)
        class LedgerRepository:
            pass

        registry = instrument(_InstrumentedApp)
        await LedgerRepository().find_all()

        assert calls(registry, "find_all") == 0.0


class TestCrudRepositoryBehaviour:
    """Repository behaviour that instrumentation must not change."""

    @pytest.mark.asyncio
    async def test_unknown_attribute_raises_query_exception(self, database):
        repository = ledger_repository()()

        with pytest.raises(QueryException, match="no attribute 'missing'"):
            repository.missing

    @pytest.mark.asyncio
    async def test_implemented_method_can_call_declared_query_methods(self, database):
        repository = ledger_repository()()
        await repository.save(LedgerEntry(account="ops", amount=5))
        await repository.save(LedgerEntry(account="ops", amount=7))
        await repository.save(LedgerEntry(account="dev", amount=100))

        assert await repository.balance("ops") == 12

    @pytest.mark.asyncio
    async def test_method_source_is_not_parsed_per_call(self, database):
        repository = ledger_repository()()

        with patch("mitsuki.data.repository.inspect.getsource") as getsource:
            await repository.find_by_account("ops")
            await repository.balance("ops")

        getsource.assert_not_called()
