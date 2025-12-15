import asyncio
import time

import pytest

from mitsuki.core.container import DIContainer, get_container, set_container
from mitsuki.core.decorators import Service
from mitsuki.core.instrumentation import (
    InstrumentationRegistry,
    Instrumented,
    _apply_instrumentation,
)
from mitsuki.core.metrics_core import MetricsStorage


class TestInstrumentationRegistry:
    """Test InstrumentationRegistry functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        set_container(DIContainer())

    def teardown_method(self):
        """Clean up after tests."""
        set_container(DIContainer())

    def test_registry_initialization(self):
        """Test that registry initializes correctly."""
        metrics_storage = MetricsStorage()
        registry = InstrumentationRegistry(metrics_storage)

        assert registry.enabled is False
        assert registry._track_memory is False
        assert registry._core is metrics_storage

    def test_registry_enable(self):
        """Test enabling instrumentation."""
        metrics_storage = MetricsStorage()
        registry = InstrumentationRegistry(metrics_storage)

        registry.enable(track_memory=False)

        assert registry.enabled is True
        assert metrics_storage.enabled is True

    def test_registry_disable(self):
        """Test disabling instrumentation."""
        metrics_storage = MetricsStorage()
        registry = InstrumentationRegistry(metrics_storage)

        registry.enable(track_memory=False)
        registry.disable()

        assert registry.enabled is False
        assert metrics_storage.enabled is False

    def test_record_http_request(self):
        """Test recording HTTP request metrics."""
        metrics_storage = MetricsStorage()
        registry = InstrumentationRegistry(metrics_storage)
        registry.enable(track_memory=False)

        registry.record_http_request("GET", "/api/users", 200, 0.5)

        counter = metrics_storage.counter("http_requests_total")
        assert (
            counter.get({"method": "GET", "path": "/api/users", "status": "200"}) == 1.0
        )

        histogram = metrics_storage.histogram("http_request_duration_seconds")
        assert histogram.get_count({"method": "GET", "path": "/api/users"}) == 1

    def test_record_http_request_disabled(self):
        """Test that metrics are not recorded when disabled."""
        metrics_storage = MetricsStorage()
        registry = InstrumentationRegistry(metrics_storage)

        registry.record_http_request("GET", "/api/users", 200, 0.5)

        assert "http_requests_total" not in metrics_storage.counters

    def test_record_component_call_success(self):
        """Test recording successful component call."""
        metrics_storage = MetricsStorage()
        registry = InstrumentationRegistry(metrics_storage)
        registry.enable(track_memory=False)

        registry.record_component_call("UserService", 0.1, error=False)

        counter = metrics_storage.counter("component_calls_total")
        assert counter.get({"component": "UserService", "status": "success"}) == 1.0

        histogram = metrics_storage.histogram("component_duration_seconds")
        assert histogram.get_count({"component": "UserService"}) == 1

    def test_record_component_call_failure(self):
        """Test recording failed component call."""
        metrics_storage = MetricsStorage()
        registry = InstrumentationRegistry(metrics_storage)
        registry.enable(track_memory=False)

        registry.record_component_call("UserService", 0.1, error=True)

        counter = metrics_storage.counter("component_calls_total")
        assert counter.get({"component": "UserService", "status": "failure"}) == 1.0


class TestInstrumentedDecorator:
    """Test @Instrumented decorator."""

    def setup_method(self):
        """Set up test fixtures."""
        set_container(DIContainer())

    def teardown_method(self):
        """Clean up after tests."""
        set_container(DIContainer())

    def test_instrumented_marks_component(self):
        """Test that @Instrumented marks component for instrumentation."""

        @Instrumented()
        @Service()
        class TestService:
            pass

        assert hasattr(TestService, "_instrumented_decorator_applied")
        assert TestService._instrumented_decorator_applied is True

    def test_instrumented_disabled(self):
        """Test that @Instrumented(enabled=False) does not instrument."""

        @Instrumented(enabled=False)
        @Service()
        class TestService:
            def method(self):
                pass

        assert TestService._instrumented_decorator_applied is False

    def test_instrumented_wraps_methods(self):
        """Test that @Instrumented wraps public methods."""

        @Instrumented()
        @Service()
        class TestService:
            def public_method(self):
                return "result"

        service = TestService()
        assert hasattr(service.public_method, "__wrapped__")

    def test_instrumented_does_not_wrap_private_methods(self):
        """Test that @Instrumented skips private methods."""

        @Instrumented()
        @Service()
        class TestService:
            def _private_method(self):
                return "private"

        service = TestService()
        assert not hasattr(service._private_method, "__wrapped__")


class TestApplyInstrumentation:
    """Test _apply_instrumentation function."""

    def setup_method(self):
        """Set up test fixtures."""
        set_container(DIContainer())

    def teardown_method(self):
        """Clean up after tests."""
        set_container(DIContainer())

    def test_apply_instrumentation_wraps_sync_method(self):
        """Test instrumenting synchronous methods."""

        class TestService:
            def get_user(self, user_id):
                return f"user_{user_id}"

        _apply_instrumentation(TestService)

        service = TestService()
        assert hasattr(service.get_user, "__wrapped__")
        assert service.get_user(123) == "user_123"

    @pytest.mark.asyncio
    async def test_apply_instrumentation_wraps_async_method(self):
        """Test instrumenting asynchronous methods."""

        class TestService:
            async def get_user(self, user_id):
                return f"user_{user_id}"

        _apply_instrumentation(TestService)

        service = TestService()
        assert hasattr(service.get_user, "__wrapped__")
        result = await service.get_user(123)
        assert result == "user_123"

    def test_apply_instrumentation_skips_dunder_methods(self):
        """Test that dunder methods are not instrumented."""

        class TestService:
            def __init__(self):
                self.value = 42

            def get_value(self):
                return self.value

        _apply_instrumentation(TestService)

        service = TestService()
        assert service.value == 42
        assert hasattr(service.get_value, "__wrapped__")

    def test_apply_instrumentation_skips_private_methods(self):
        """Test that private methods are not instrumented."""

        class TestService:
            def _internal_method(self):
                return "internal"

            def public_method(self):
                return "public"

        _apply_instrumentation(TestService)

        service = TestService()
        assert not hasattr(service._internal_method, "__wrapped__")
        assert hasattr(service.public_method, "__wrapped__")


class TestInstrumentationMetrics:
    """Test that instrumentation records metrics correctly."""

    def setup_method(self):
        """Set up test fixtures."""
        set_container(DIContainer())

    def teardown_method(self):
        """Clean up after tests."""
        set_container(DIContainer())

    def test_sync_method_records_metrics(self):
        """Test that sync methods record execution metrics."""
        registry = get_container().get(InstrumentationRegistry)
        metrics_storage = get_container().get(MetricsStorage)
        registry.enable(track_memory=False)

        @Service()
        class TestService:
            def slow_operation(self):
                time.sleep(0.01)
                return "done"

        service = get_container().get(TestService)
        result = service.slow_operation()

        assert result == "done"

        counter = metrics_storage.counter("component_calls_total")
        assert counter.get({"component": "TestService", "status": "success"}) == 1.0

        histogram = metrics_storage.histogram("component_duration_seconds")
        assert histogram.get_count({"component": "TestService"}) == 1
        assert histogram.get_sum({"component": "TestService"}) > 0.01

    @pytest.mark.asyncio
    async def test_async_method_records_metrics(self):
        """Test that async methods record execution metrics."""
        registry = get_container().get(InstrumentationRegistry)
        metrics_storage = get_container().get(MetricsStorage)
        registry.enable(track_memory=False)

        @Service()
        class TestService:
            async def async_operation(self):
                await asyncio.sleep(0.01)
                return "done"

        service = get_container().get(TestService)
        result = await service.async_operation()

        assert result == "done"

        counter = metrics_storage.counter("component_calls_total")
        assert counter.get({"component": "TestService", "status": "success"}) == 1.0

        histogram = metrics_storage.histogram("component_duration_seconds")
        assert histogram.get_count({"component": "TestService"}) == 1

    def test_method_error_records_failure_metric(self):
        """Test that method errors are recorded as failures."""
        registry = get_container().get(InstrumentationRegistry)
        metrics_storage = get_container().get(MetricsStorage)
        registry.enable(track_memory=False)

        @Service()
        class TestService:
            def failing_method(self):
                raise ValueError("test error")

        service = get_container().get(TestService)

        with pytest.raises(ValueError, match="test error"):
            service.failing_method()

        counter = metrics_storage.counter("component_calls_total")
        assert counter.get({"component": "TestService", "status": "failure"}) == 1.0

    @pytest.mark.asyncio
    async def test_async_method_error_records_failure_metric(self):
        """Test that async method errors are recorded as failures."""
        registry = get_container().get(InstrumentationRegistry)
        metrics_storage = get_container().get(MetricsStorage)
        registry.enable(track_memory=False)

        @Service()
        class TestService:
            async def failing_async_method(self):
                raise ValueError("async test error")

        service = get_container().get(TestService)

        with pytest.raises(ValueError, match="async test error"):
            await service.failing_async_method()

        counter = metrics_storage.counter("component_calls_total")
        assert counter.get({"component": "TestService", "status": "failure"}) == 1.0

    def test_instrumentation_disabled_no_metrics(self):
        """Test that no metrics are recorded when instrumentation is disabled."""
        registry = get_container().get(InstrumentationRegistry)
        metrics_storage = get_container().get(MetricsStorage)

        @Service()
        class TestService:
            def operation(self):
                return "done"

        service = get_container().get(TestService)
        result = service.operation()

        assert result == "done"
        assert "component_calls_total" not in metrics_storage.counters

    def test_multiple_calls_accumulate_metrics(self):
        """Test that multiple calls accumulate in metrics."""
        registry = get_container().get(InstrumentationRegistry)
        metrics_storage = get_container().get(MetricsStorage)
        registry.enable(track_memory=False)

        @Service()
        class TestService:
            def operation(self):
                return "done"

        service = get_container().get(TestService)

        for _ in range(5):
            service.operation()

        counter = metrics_storage.counter("component_calls_total")
        assert counter.get({"component": "TestService", "status": "success"}) == 5.0

        histogram = metrics_storage.histogram("component_duration_seconds")
        assert histogram.get_count({"component": "TestService"}) == 5


class TestInstrumentationProvider:
    """Test InstrumentationProvider component."""

    def setup_method(self):
        """Set up test fixtures."""
        set_container(DIContainer())

    def teardown_method(self):
        """Clean up after tests."""
        set_container(DIContainer())

    def test_provider_can_be_injected(self):
        """Test that InstrumentationProvider can be injected."""
        from mitsuki.core.instrumentation import InstrumentationProvider

        container = get_container()
        container.register(InstrumentationProvider)

        provider = container.get(InstrumentationProvider)
        assert provider is not None
        assert hasattr(provider, "record_metric")

    def test_record_custom_metric(self):
        """Test recording custom metrics via provider."""
        from mitsuki.core.instrumentation import InstrumentationProvider

        registry = get_container().get(InstrumentationRegistry)
        metrics_storage = get_container().get(MetricsStorage)
        registry.enable(track_memory=False)

        container = get_container()
        container.register(InstrumentationProvider)
        provider = container.get(InstrumentationProvider)

        provider.record_metric("user_registrations", 1, {"source": "web"})

        counter = metrics_storage.counter("user_registrations")
        assert counter.get({"source": "web"}) == 1.0

    def test_record_custom_metric_disabled(self):
        """Test that custom metrics are not recorded when disabled."""
        from mitsuki.core.instrumentation import InstrumentationProvider

        metrics_storage = get_container().get(MetricsStorage)

        container = get_container()
        container.register(InstrumentationProvider)
        provider = container.get(InstrumentationProvider)

        provider.record_metric("user_registrations", 1, {"source": "web"})

        assert "user_registrations" not in metrics_storage.counters
