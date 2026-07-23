import asyncio

import pytest

from mitsuki.core.container import DIContainer, get_container, set_container
from mitsuki.core.decorators import Service
from mitsuki.core.instrumentation import (
    InstrumentationProvider,
    InstrumentationRegistry,
    Instrumented,
    apply_instrumentation,
)
from mitsuki.core.metrics_core import MetricsStorage


class _App:
    """Stand-in for an @Application class with no application-wide opt-in."""


def _enabled_registry(storage=None) -> InstrumentationRegistry:
    registry = InstrumentationRegistry(storage or MetricsStorage())
    registry._core.enable()
    registry.enable(track_memory=False)
    return registry


class TestInstrumentationRegistry:
    """Recording of HTTP and component metrics."""

    def setup_method(self):
        self._previous_container = get_container()
        set_container(DIContainer())

    def teardown_method(self):
        set_container(self._previous_container)

    def test_registry_initialization(self):
        metrics_storage = MetricsStorage()
        registry = InstrumentationRegistry(metrics_storage)

        assert registry.enabled is False
        assert registry._track_memory is False
        assert registry._core is metrics_storage

    def test_registry_enable(self):
        registry = InstrumentationRegistry(MetricsStorage())
        registry.enable(track_memory=False)

        assert registry.enabled is True

    def test_registry_disable(self):
        registry = InstrumentationRegistry(MetricsStorage())
        registry.enable(track_memory=False)
        registry.disable()

        assert registry.enabled is False

    def test_record_http_request(self):
        registry = _enabled_registry()
        registry.record_http_request("GET", "/api/users", 200, 0.5)

        counter = registry._core.counter("http_requests_total")
        assert (
            counter.get({"method": "GET", "path": "/api/users", "status": "200"}) == 1.0
        )

        histogram = registry._core.histogram("http_request_duration_seconds")
        assert histogram.get_count({"method": "GET", "path": "/api/users"}) == 1

    def test_record_http_request_disabled(self):
        registry = InstrumentationRegistry(MetricsStorage())
        registry.record_http_request("GET", "/api/users", 200, 0.5)

        assert "http_requests_total" not in registry._core.counters

    def test_record_component_call_success(self):
        registry = _enabled_registry()
        registry.record_component_call("UserService", "get_user", 0.1, error=False)

        counter = registry._core.counter("component_calls_total")
        assert (
            counter.get(
                {"component": "UserService", "method": "get_user", "status": "success"}
            )
            == 1.0
        )

        histogram = registry._core.histogram("component_duration_seconds")
        assert histogram.get_count({"component": "UserService", "method": "get_user"}) == 1

    def test_record_component_call_failure(self):
        registry = _enabled_registry()
        registry.record_component_call("UserService", "get_user", 0.1, error=True)

        counter = registry._core.counter("component_calls_total")
        assert (
            counter.get(
                {"component": "UserService", "method": "get_user", "status": "failure"}
            )
            == 1.0
        )

    def test_record_component_call_disabled(self):
        registry = InstrumentationRegistry(MetricsStorage())
        registry.record_component_call("UserService", "get_user", 0.1)

        assert "component_calls_total" not in registry._core.counters


class TestInstrumentedDecorator:
    """@Instrumented markers on components."""

    def setup_method(self):
        self._previous_container = get_container()
        set_container(DIContainer())

    def teardown_method(self):
        set_container(self._previous_container)

    def test_instrumented_marks_component(self):
        @Instrumented()
        @Service()
        class MarkedService:
            pass

        assert MarkedService._instrumented_decorator_applied is True

    def test_instrumented_disabled_marks_component(self):
        @Instrumented(enabled=False)
        @Service()
        class UnmarkedService:
            def method(self):
                pass

        assert UnmarkedService._instrumented_decorator_applied is False


class TestInstrumentedMethods:
    """Method wrapping applied by apply_instrumentation."""

    def setup_method(self):
        self._previous_container = get_container()
        set_container(DIContainer())

    def teardown_method(self):
        set_container(self._previous_container)

    def test_sync_method_records_metrics(self):
        @Instrumented()
        @Service()
        class SyncService:
            def work(self):
                return "done"

        registry = _enabled_registry()
        apply_instrumentation(_App, registry)

        assert SyncService().work() == "done"
        assert (
            registry._core.counter("component_calls_total").get(
                {"component": "SyncService", "method": "work", "status": "success"}
            )
            == 1.0
        )

    def test_async_method_records_metrics(self):
        @Instrumented()
        @Service()
        class AsyncService:
            async def work(self):
                return "done"

        registry = _enabled_registry()
        apply_instrumentation(_App, registry)

        assert asyncio.run(AsyncService().work()) == "done"
        assert (
            registry._core.counter("component_calls_total").get(
                {"component": "AsyncService", "method": "work", "status": "success"}
            )
            == 1.0
        )

    def test_method_error_records_failure_and_propagates(self):
        @Instrumented()
        @Service()
        class FailingService:
            def work(self):
                raise ValueError("boom")

        registry = _enabled_registry()
        apply_instrumentation(_App, registry)

        with pytest.raises(ValueError, match="boom"):
            FailingService().work()

        assert (
            registry._core.counter("component_calls_total").get(
                {"component": "FailingService", "method": "work", "status": "failure"}
            )
            == 1.0
        )

    def test_async_method_error_records_failure_and_propagates(self):
        @Instrumented()
        @Service()
        class FailingAsyncService:
            async def work(self):
                raise ValueError("boom")

        registry = _enabled_registry()
        apply_instrumentation(_App, registry)

        with pytest.raises(ValueError, match="boom"):
            asyncio.run(FailingAsyncService().work())

        assert (
            registry._core.counter("component_calls_total").get(
                {
                    "component": "FailingAsyncService",
                    "method": "work",
                    "status": "failure",
                }
            )
            == 1.0
        )

    def test_dunder_and_private_methods_are_skipped(self):
        @Instrumented()
        @Service()
        class MixedService:
            def __len__(self):
                return 0

            def _private(self):
                return "private"

            def public(self):
                return "public"

        registry = _enabled_registry()
        apply_instrumentation(_App, registry)

        instance = MixedService()
        len(instance)
        instance._private()
        instance.public()

        recorded = {
            sample.labels["method"]
            for sample in registry._core.counter("component_calls_total").samples()
        }
        assert recorded == {"public"}

    def test_disabled_instrumentation_records_nothing(self):
        @Instrumented()
        @Service()
        class QuietService:
            def work(self):
                return "done"

        registry = InstrumentationRegistry(MetricsStorage())
        apply_instrumentation(_App, registry)

        assert QuietService().work() == "done"
        assert "component_calls_total" not in registry._core.counters

    def test_multiple_calls_accumulate(self):
        @Instrumented()
        @Service()
        class CountingService:
            def work(self):
                return "done"

        registry = _enabled_registry()
        apply_instrumentation(_App, registry)

        instance = CountingService()
        for _ in range(3):
            instance.work()

        assert (
            registry._core.counter("component_calls_total").get(
                {"component": "CountingService", "method": "work", "status": "success"}
            )
            == 3.0
        )


class TestInstrumentationProvider:
    """Custom metrics recorded through InstrumentationProvider."""

    def setup_method(self):
        self._previous_container = get_container()
        set_container(DIContainer())

    def teardown_method(self):
        set_container(self._previous_container)

    def test_record_custom_metric(self):
        storage = MetricsStorage()
        storage.enable()
        provider = InstrumentationProvider(storage)

        provider.record_metric("user_registrations", 1, {"source": "web"})

        assert storage.counter("user_registrations").get({"source": "web"}) == 1.0

    def test_record_custom_metric_accumulates(self):
        storage = MetricsStorage()
        storage.enable()
        provider = InstrumentationProvider(storage)

        provider.record_metric("rows_returned", 5, {"table": "users"})
        provider.record_metric("rows_returned", 3, {"table": "users"})

        assert storage.counter("rows_returned").get({"table": "users"}) == 8.0

    def test_record_custom_metric_disabled(self):
        storage = MetricsStorage()
        provider = InstrumentationProvider(storage)

        provider.record_metric("user_registrations", 1, {"source": "web"})

        assert "user_registrations" not in storage.counters
