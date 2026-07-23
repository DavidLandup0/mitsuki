from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from mitsuki.core.application import ApplicationContext
from mitsuki.core.container import DIContainer, get_container, set_container
from mitsuki.core.metrics import create_metrics_endpoint
from mitsuki.core.decorators import Service
from mitsuki.core.instrumentation import (
    InstrumentationRegistry,
    Instrumented,
    apply_instrumentation,
)
from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.core.metrics_formatters import format_json, format_prometheus
from mitsuki.web.controllers import RestController, get_all_controllers


def _registry() -> InstrumentationRegistry:
    return InstrumentationRegistry(MetricsStorage())


class TestComponentDecoration:
    """Stereotype decorators run at import time, before the container exists."""

    def setup_method(self):
        self._previous_container = get_container()
        set_container(DIContainer())

    def teardown_method(self):
        set_container(self._previous_container)

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


class TestInstrumentedSelectivity:
    """@Instrumented selects which components are instrumented."""

    def setup_method(self):
        self._previous_container = get_container()
        set_container(DIContainer())

    def teardown_method(self):
        set_container(self._previous_container)

    def test_unmarked_component_is_not_instrumented(self):
        @Service()
        class CacheWarmer:
            def warm_cache(self):
                return "warm"

        class App:
            pass

        registry = _registry()
        registry.enable()
        apply_instrumentation(App, registry)

        CacheWarmer().warm_cache()

        assert (
            registry._core.counter("component_calls_total").get(
                {"component": "CacheWarmer", "method": "warm_cache", "status": "success"}
            )
            == 0.0
        )

    def test_component_level_opt_in_instruments_only_that_component(self):
        @Instrumented()
        @Service()
        class PaymentService:
            def charge(self):
                return "ok"

        @Service()
        class EmailService:
            def send(self):
                return "sent"

        class App:
            pass

        registry = _registry()
        registry.enable()
        apply_instrumentation(App, registry)

        PaymentService().charge()
        EmailService().send()

        calls = registry._core.counter("component_calls_total")
        assert (
            calls.get(
                {"component": "PaymentService", "method": "charge", "status": "success"}
            )
            == 1.0
        )
        assert (
            calls.get(
                {"component": "EmailService", "method": "send", "status": "success"}
            )
            == 0.0
        )

    def test_application_level_instruments_every_component(self):
        @Service()
        class OrderService:
            def create(self):
                return "created"

        @Instrumented()
        class App:
            __mitsuki_application__ = True

        registry = _registry()
        registry.enable()
        apply_instrumentation(App, registry)

        OrderService().create()

        assert (
            registry._core.counter("component_calls_total").get(
                {"component": "OrderService", "method": "create", "status": "success"}
            )
            == 1.0
        )

    def test_component_opts_out_of_application_level(self):
        @Instrumented(enabled=False)
        @Service()
        class HotPathService:
            def tick(self):
                return "tick"

        @Instrumented()
        class App:
            __mitsuki_application__ = True

        registry = _registry()
        registry.enable()
        apply_instrumentation(App, registry)

        HotPathService().tick()

        assert (
            registry._core.counter("component_calls_total").get(
                {"component": "HotPathService", "method": "tick", "status": "success"}
            )
            == 0.0
        )

    def test_private_methods_are_not_instrumented(self):
        @Instrumented()
        @Service()
        class UserService:
            def _internal_helper(self):
                return "internal"

        class App:
            pass

        registry = _registry()
        registry.enable()
        apply_instrumentation(App, registry)

        UserService()._internal_helper()

        assert registry._core.counter("component_calls_total").samples() == []


class TestDescriptorBinding:
    """Instrumentation preserves how methods bind to class and instance."""

    def setup_method(self):
        self._previous_container = get_container()
        set_container(DIContainer())

    def teardown_method(self):
        set_container(self._previous_container)

    def _instrument(self, cls):
        class App:
            pass

        registry = _registry()
        registry.enable()
        apply_instrumentation(App, registry)
        return registry

    def test_staticmethod_binds_on_class_and_instance(self):
        @Instrumented()
        @Service()
        class MathService:
            @staticmethod
            def double(x):
                return x * 2

        self._instrument(MathService)

        assert MathService.double(3) == 6
        assert MathService().double(3) == 6

    def test_classmethod_binds_on_class_and_instance(self):
        @Instrumented()
        @Service()
        class BuilderService:
            @classmethod
            def name(cls):
                return cls.__name__

        self._instrument(BuilderService)

        assert BuilderService.name() == "BuilderService"
        assert BuilderService().name() == "BuilderService"

    def test_property_remains_a_property(self):
        @Instrumented()
        @Service()
        class ConfigService:
            @property
            def value(self):
                return 42

        self._instrument(ConfigService)

        assert ConfigService().value == 42


class TestComponentLabels:
    """Component metrics carry both component and method labels."""

    def test_methods_are_recorded_separately(self):
        registry = _registry()
        registry.enable()

        registry.record_component_call("UserService", "get_user", 0.1)
        registry.record_component_call("UserService", "get_user", 0.1)
        registry.record_component_call("UserService", "delete_user", 0.2, error=True)

        calls = registry._core.counter("component_calls_total")
        assert (
            calls.get(
                {"component": "UserService", "method": "get_user", "status": "success"}
            )
            == 2.0
        )
        assert (
            calls.get(
                {
                    "component": "UserService",
                    "method": "delete_user",
                    "status": "failure",
                }
            )
            == 1.0
        )


class TestRenderingGate:
    """Rendering is gated on metrics being enabled, independently of instrumentation."""

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
        registry = _registry()
        registry.enable(track_memory=False)

        assert "system_memory_bytes" in registry._core.gauges
        assert "system_cpu_percent" in registry._core.gauges
        assert "system_traced_memory_bytes" not in registry._core.gauges

    def test_track_memory_adds_traced_memory(self):
        registry = _registry()
        registry.enable(track_memory=True)
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

    def setup_method(self):
        self._previous_container = get_container()
        set_container(DIContainer())
        get_container().register(MetricsStorage, name="MetricsStorage")

    def teardown_method(self):
        set_container(self._previous_container)

    def test_metrics_controller_is_registered_before_controllers_collected(self):
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
