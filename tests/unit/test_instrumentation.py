import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from starlette.routing import Mount, Route

import mitsuki.core.decorators as decorators
from mitsuki.core.application import ApplicationContext
from mitsuki.core.container import get_container
from mitsuki.core.decorators import Service
from mitsuki.core.instrumentation import (
    InstrumentationMiddleware,
    InstrumentationProvider,
    InstrumentationRegistry,
    Instrumented,
    apply_instrumentation,
    build_route_map,
)
from mitsuki.core.metrics import create_metrics_endpoint
from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.core.metrics_formatters import format_json, format_prometheus
from mitsuki.web.controllers import RestController, get_all_controllers


class _App:
    """An @Application with no application-wide instrumentation."""


@pytest.fixture(autouse=True)
def _isolate(isolated_container):
    """
    Isolate every test: a fresh container plus an empty set of instrumentable
    components, so decorations in one test never leak into another.
    """
    saved = list(decorators._instrumentable_components)
    decorators._instrumentable_components.clear()
    try:
        yield
    finally:
        decorators._instrumentable_components[:] = saved


def enabled_registry(track_memory: bool = False) -> InstrumentationRegistry:
    registry = InstrumentationRegistry(MetricsStorage())
    registry.enable(track_memory=track_memory)
    return registry


def instrument(app_cls=_App, *, track_memory: bool = False) -> InstrumentationRegistry:
    """Enable a registry and apply instrumentation for the given application."""
    registry = enabled_registry(track_memory=track_memory)
    apply_instrumentation(app_cls, registry)
    return registry


def calls(registry, component, method, status="success") -> float:
    return registry._core.counter("component_calls_total").get(
        {"component": component, "method": method, "status": status}
    )


class TestRegistryRecording:
    """The registry records HTTP and component metrics while enabled."""

    def test_initialization(self):
        storage = MetricsStorage()
        registry = InstrumentationRegistry(storage)

        assert registry.enabled is False
        assert registry._track_memory is False
        assert registry._core is storage

    def test_enable_and_disable(self):
        registry = InstrumentationRegistry(MetricsStorage())

        registry.enable(track_memory=False)
        assert registry.enabled is True

        registry.disable()
        assert registry.enabled is False

    def test_record_http_request(self):
        registry = enabled_registry()
        registry.record_http_request("GET", "/api/users", 200, 0.5)

        counter = registry._core.counter("http_requests_total")
        assert (
            counter.get({"method": "GET", "path": "/api/users", "status": "200"}) == 1.0
        )
        histogram = registry._core.histogram("http_request_duration_seconds")
        assert histogram.get_count({"method": "GET", "path": "/api/users"}) == 1

    def test_record_http_request_ignored_when_disabled(self):
        registry = InstrumentationRegistry(MetricsStorage())
        registry.record_http_request("GET", "/api/users", 200, 0.5)

        assert "http_requests_total" not in registry._core.counters

    def test_record_component_call_success(self):
        registry = enabled_registry()
        registry.record_component_call("UserService", "get_user", 0.1)

        assert calls(registry, "UserService", "get_user") == 1.0
        histogram = registry._core.histogram("component_duration_seconds")
        assert histogram.get_count({"component": "UserService", "method": "get_user"}) == 1

    def test_record_component_call_failure(self):
        registry = enabled_registry()
        registry.record_component_call("UserService", "get_user", 0.1, error=True)

        assert calls(registry, "UserService", "get_user", "failure") == 1.0

    def test_record_component_call_ignored_when_disabled(self):
        registry = InstrumentationRegistry(MetricsStorage())
        registry.record_component_call("UserService", "get_user", 0.1)

        assert "component_calls_total" not in registry._core.counters

    def test_methods_recorded_under_separate_labels(self):
        registry = enabled_registry()
        registry.record_component_call("UserService", "get_user", 0.1)
        registry.record_component_call("UserService", "get_user", 0.1)
        registry.record_component_call("UserService", "delete_user", 0.2, error=True)

        assert calls(registry, "UserService", "get_user") == 2.0
        assert calls(registry, "UserService", "delete_user", "failure") == 1.0


class TestComponentDecoration:
    """Stereotype decorators run at import time, before the container exists."""

    def test_service_decorates_with_empty_container(self):
        @Service()
        class UserService:
            def get_user(self, user_id: int):
                return user_id

        assert UserService().get_user(7) == 7

    def test_controller_decorates_with_empty_container(self):
        @RestController("/api")
        class UserController:
            def list_users(self):
                return []

        assert UserController().list_users() == []


class TestInstrumentedMarker:
    """@Instrumented records the opt-in choice on the class."""

    def test_marks_component_enabled(self):
        @Instrumented()
        @Service()
        class MarkedService:
            pass

        assert MarkedService._instrumented_decorator_applied is True

    def test_marks_component_disabled(self):
        @Instrumented(enabled=False)
        @Service()
        class UnmarkedService:
            pass

        assert UnmarkedService._instrumented_decorator_applied is False


class TestInstrumentedSelectivity:
    """@Instrumented decides which components get instrumented."""

    def test_unmarked_component_is_not_instrumented(self):
        @Service()
        class CacheWarmer:
            def warm_cache(self):
                return "warm"

        registry = instrument()
        CacheWarmer().warm_cache()

        assert calls(registry, "CacheWarmer", "warm_cache") == 0.0

    def test_component_opt_in_instruments_only_that_component(self):
        @Instrumented()
        @Service()
        class PaymentService:
            def charge(self):
                return "ok"

        @Service()
        class EmailService:
            def send(self):
                return "sent"

        registry = instrument()
        PaymentService().charge()
        EmailService().send()

        assert calls(registry, "PaymentService", "charge") == 1.0
        assert calls(registry, "EmailService", "send") == 0.0

    def test_application_opt_in_instruments_every_component(self):
        @Service()
        class OrderService:
            def create(self):
                return "created"

        @Instrumented()
        class App:
            __mitsuki_application__ = True

        registry = instrument(App)
        OrderService().create()

        assert calls(registry, "OrderService", "create") == 1.0

    def test_component_opts_out_of_application_instrumentation(self):
        @Instrumented(enabled=False)
        @Service()
        class HotPathService:
            def tick(self):
                return "tick"

        @Instrumented()
        class App:
            __mitsuki_application__ = True

        registry = instrument(App)
        HotPathService().tick()

        assert calls(registry, "HotPathService", "tick") == 0.0

    def test_private_methods_are_not_instrumented(self):
        @Instrumented()
        @Service()
        class UserService:
            def _internal_helper(self):
                return "internal"

        registry = instrument()
        UserService()._internal_helper()

        assert registry._core.counter("component_calls_total").samples() == []


class TestWrappingMechanics:
    """Wrapped methods record timing, propagate errors and skip dunders."""

    def test_sync_method_records(self):
        @Instrumented()
        @Service()
        class SyncService:
            def work(self):
                return "done"

        registry = instrument()

        assert SyncService().work() == "done"
        assert calls(registry, "SyncService", "work") == 1.0

    def test_async_method_records(self):
        @Instrumented()
        @Service()
        class AsyncService:
            async def work(self):
                return "done"

        registry = instrument()

        assert asyncio.run(AsyncService().work()) == "done"
        assert calls(registry, "AsyncService", "work") == 1.0

    def test_sync_error_propagates_and_records_failure(self):
        @Instrumented()
        @Service()
        class FailingService:
            def work(self):
                raise ValueError("boom")

        registry = instrument()

        with pytest.raises(ValueError, match="boom"):
            FailingService().work()

        assert calls(registry, "FailingService", "work", "failure") == 1.0

    def test_async_error_propagates_and_records_failure(self):
        @Instrumented()
        @Service()
        class FailingAsyncService:
            async def work(self):
                raise ValueError("boom")

        registry = instrument()

        with pytest.raises(ValueError, match="boom"):
            asyncio.run(FailingAsyncService().work())

        assert calls(registry, "FailingAsyncService", "work", "failure") == 1.0

    def test_dunder_methods_are_skipped(self):
        @Instrumented()
        @Service()
        class SizedService:
            def __len__(self):
                return 0

            def public(self):
                return "public"

        registry = instrument()
        instance = SizedService()
        len(instance)
        instance.public()

        recorded = {
            s.labels["method"]
            for s in registry._core.counter("component_calls_total").samples()
        }
        assert recorded == {"public"}

    def test_multiple_calls_accumulate(self):
        @Instrumented()
        @Service()
        class CountingService:
            def work(self):
                return "done"

        registry = instrument()
        instance = CountingService()
        for _ in range(3):
            instance.work()

        assert calls(registry, "CountingService", "work") == 3.0

    def test_wrapped_method_records_nothing_while_disabled(self):
        @Instrumented()
        @Service()
        class QuietService:
            def work(self):
                return "done"

        registry = InstrumentationRegistry(MetricsStorage())
        apply_instrumentation(_App, registry)

        assert QuietService().work() == "done"
        assert "component_calls_total" not in registry._core.counters


class TestDescriptorBinding:
    """Instrumentation preserves how methods bind to class and instance."""

    def test_staticmethod_binds_on_class_and_instance(self):
        @Instrumented()
        @Service()
        class MathService:
            @staticmethod
            def double(x):
                return x * 2

        instrument()

        assert MathService.double(3) == 6
        assert MathService().double(3) == 6

    def test_classmethod_binds_on_class_and_instance(self):
        @Instrumented()
        @Service()
        class BuilderService:
            @classmethod
            def name(cls):
                return cls.__name__

        instrument()

        assert BuilderService.name() == "BuilderService"
        assert BuilderService().name() == "BuilderService"

    def test_property_remains_a_property(self):
        @Instrumented()
        @Service()
        class ConfigService:
            @property
            def value(self):
                return 42

        instrument()

        assert ConfigService().value == 42


class TestCustomMetricsProvider:
    """InstrumentationProvider records custom counters when metrics are enabled."""

    def test_record_metric(self):
        storage = MetricsStorage()
        storage.enable()
        provider = InstrumentationProvider(storage)

        provider.record_metric("user_registrations", 1, {"source": "web"})

        assert storage.counter("user_registrations").get({"source": "web"}) == 1.0

    def test_record_metric_accumulates(self):
        storage = MetricsStorage()
        storage.enable()
        provider = InstrumentationProvider(storage)

        provider.record_metric("rows_returned", 5, {"table": "users"})
        provider.record_metric("rows_returned", 3, {"table": "users"})

        assert storage.counter("rows_returned").get({"table": "users"}) == 8.0

    def test_record_metric_ignored_when_disabled(self):
        storage = MetricsStorage()
        provider = InstrumentationProvider(storage)

        provider.record_metric("user_registrations", 1, {"source": "web"})

        assert "user_registrations" not in storage.counters


class TestRenderingGate:
    """Rendering is gated on metrics, independently of instrumentation."""

    def test_scheduler_metrics_render_without_instrumentation(self):
        storage = MetricsStorage()
        storage.enable()
        storage.counter("scheduler_task_executions_total", "x").inc(
            {"task": "Bg.cleanup", "status": "success"}
        )
        storage.histogram("scheduler_task_duration_seconds", "x").observe(
            0.01, {"task": "Bg.cleanup"}
        )

        rendered = format_json(storage)

        assert rendered["enabled"] is True
        assert rendered["scheduler"]["tasks"][0]["name"] == "Bg.cleanup"
        assert "scheduler_task_executions_total" in format_prometheus(storage)

    def test_custom_metrics_render_without_instrumentation(self):
        storage = MetricsStorage()
        storage.enable()
        storage.counter("orders_created_total", "x").inc({"source": "api"})

        assert "orders_created_total" in format_prometheus(storage)


class TestPrometheusLabelEscaping:
    """Label values are user-controlled and cannot break the exposition format."""

    @pytest.mark.parametrize(
        "value",
        [
            '/x"} 999\ninjected_metric{a="b',
            "/back\\slash",
            "/new\nline",
        ],
    )
    def test_label_values_cannot_inject_metrics(self, value):
        storage = MetricsStorage()
        storage.enable()
        storage.counter("http_requests_total", "Total").inc({"path": value})

        output = format_prometheus(storage)
        metric_lines = [
            line for line in output.splitlines() if line and not line.startswith("#")
        ]

        assert len(metric_lines) == 1
        assert metric_lines[0].startswith("http_requests_total{")
        assert "\n" not in metric_lines[0].split("} ")[0]


class TestSystemMetrics:
    """CPU and memory always sample; track_memory adds traced memory."""

    def test_cpu_and_memory_sample_without_track_memory(self):
        registry = enabled_registry(track_memory=False)

        assert "system_memory_bytes" in registry._core.gauges
        assert "system_cpu_percent" in registry._core.gauges
        assert "system_traced_memory_bytes" not in registry._core.gauges

    def test_track_memory_adds_traced_memory(self):
        registry = enabled_registry(track_memory=True)
        try:
            assert "system_memory_bytes" in registry._core.gauges
            assert "system_cpu_percent" in registry._core.gauges
            assert "system_traced_memory_bytes" in registry._core.gauges
        finally:
            registry.disable()


class TestMetricsEndpointRegistrationOrder:
    """
    The metrics endpoints are registered by a @RestController created inside
    initialize_metrics, so they only reach the route table if that runs before
    controllers are collected.
    """

    def test_metrics_controller_registered_before_controllers_collected(self):
        get_container().register(MetricsStorage, name="MetricsStorage")

        config = Mock()
        config.get_bool.side_effect = lambda key, default=None: {
            "metrics.enabled": True,
            "instrumentation.enabled": False,
        }.get(key, False)
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": [],
        }.get(key, default)

        context = SimpleNamespace(
            container=get_container(),
            application_class=type("App", (), {}),
            _register_metrics_endpoint=lambda: create_metrics_endpoint(config),
        )

        with patch("mitsuki.core.application.get_config", return_value=config):
            ApplicationContext.initialize_metrics(context)

        registered = {cls.__name__ for cls, _ in get_all_controllers()}
        assert "MetricsController" in registered


def _endpoint():
    return None


async def _run_asgi(mw, scope, status=200):
    async def receive():
        return {"type": "http.request"}

    async def send(message):
        pass

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status})
        await send({"type": "http.response.body", "body": b""})

    mw.app = app
    await mw(scope, receive, send)


class TestRouteMap:
    """build_route_map maps route endpoints to their path templates."""

    def test_maps_endpoint_to_template(self):
        route = Route("/users/{user_id}", _endpoint)

        assert build_route_map([route]) == {_endpoint: "/users/{user_id}"}

    def test_skips_non_route_entries(self):
        mount = Mount("/static", routes=[])
        route = Route("/health", _endpoint)

        mapping = build_route_map([mount, route])

        assert mapping == {_endpoint: "/health"}


class TestHttpMiddleware:
    """The middleware labels requests by matched route template."""

    def test_records_matched_route_template(self):
        registry = enabled_registry()
        mw = InstrumentationMiddleware(
            None, registry, {_endpoint: "/users/{user_id}"}
        )

        asyncio.run(
            _run_asgi(mw, {"type": "http", "method": "GET", "endpoint": _endpoint})
        )

        counter = registry._core.counter("http_requests_total")
        assert (
            counter.get(
                {"method": "GET", "path": "/users/{user_id}", "status": "200"}
            )
            == 1.0
        )

    def test_unmatched_request_falls_back(self):
        registry = enabled_registry()
        mw = InstrumentationMiddleware(None, registry, {})

        asyncio.run(_run_asgi(mw, {"type": "http", "method": "GET"}, status=404))

        counter = registry._core.counter("http_requests_total")
        assert (
            counter.get({"method": "GET", "path": "<unmatched>", "status": "404"})
            == 1.0
        )

    def test_non_http_scope_is_not_recorded(self):
        registry = enabled_registry()
        mw = InstrumentationMiddleware(None, registry, {})

        asyncio.run(_run_asgi(mw, {"type": "lifespan"}))

        assert registry._core.counter("http_requests_total").samples() == []

    def test_disabled_registry_is_not_recorded(self):
        registry = InstrumentationRegistry(MetricsStorage())
        mw = InstrumentationMiddleware(None, registry, {})

        asyncio.run(
            _run_asgi(mw, {"type": "http", "method": "GET", "endpoint": _endpoint})
        )

        assert "http_requests_total" not in registry._core.counters


class TestSystemMetricSampling:
    """A single sample populates the system gauges."""

    def test_sample_sets_cpu_and_memory(self):
        registry = enabled_registry(track_memory=False)
        registry._sample_once()

        assert registry._core.gauge("system_memory_bytes").get({"type": "rss"}) > 0
        assert registry._core.gauge("system_memory_bytes").get({"type": "vms"}) > 0
        assert registry._core.gauge("system_traced_memory_bytes").samples() == []

    def test_sample_sets_traced_memory_when_enabled(self):
        registry = enabled_registry(track_memory=True)
        try:
            registry._sample_once()

            traced = registry._core.gauge("system_traced_memory_bytes")
            assert traced.get({"type": "current"}) > 0
            assert traced.get({"type": "peak"}) > 0
        finally:
            registry.disable()


class TestBackgroundCollection:
    """The background sampler starts, samples, and stops with the registry."""

    def test_start_samples_then_stop_cancels(self):
        registry = enabled_registry()

        async def scenario():
            registry.start_background_collection()
            assert registry._background_task is not None
            await asyncio.sleep(0.01)
            registry.stop_background_collection()
            assert registry._background_task is None

        asyncio.run(scenario())

        assert registry._core.gauge("system_memory_bytes").get({"type": "rss"}) > 0

    def test_start_is_idempotent(self):
        registry = enabled_registry()

        async def scenario():
            registry.start_background_collection()
            first = registry._background_task
            registry.start_background_collection()
            assert registry._background_task is first
            registry.stop_background_collection()

        asyncio.run(scenario())

    def test_disabled_registry_starts_no_task(self):
        registry = InstrumentationRegistry(MetricsStorage())

        async def scenario():
            registry.start_background_collection()
            assert registry._background_task is None

        asyncio.run(scenario())


class TestApplyIdempotency:
    """A component is instrumented at most once, even across repeated applies."""

    def test_second_apply_does_not_double_wrap(self):
        @Instrumented()
        @Service()
        class Svc:
            def work(self):
                return "x"

        registry = instrument()
        apply_instrumentation(_App, registry)  # second pass skips already-applied

        Svc().work()

        assert calls(registry, "Svc", "work") == 1.0
