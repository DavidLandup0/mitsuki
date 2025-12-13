"""
Instrumentation and metrics collection for Mitsuki components.

Provides decorators and utilities for tracking:
- Request/response metrics (latency, throughput, status codes)
- Memory usage (heap, RSS)
- CPU usage
- Component-level performance
"""

import asyncio
import functools
import threading
import time
import tracemalloc
from datetime import datetime
from typing import Callable, Optional

import psutil

from mitsuki.core.decorators import Provider
from mitsuki.core.metrics_core import MetricsRegistry as CoreMetricsRegistry


class MetricsRegistry:
    """
    Instrumentation registry that uses core metrics.
    Thread-safe singleton for collecting and exposing metrics.
    """

    _instance: Optional["MetricsRegistry"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.enabled: bool = False
        self.start_time: datetime = datetime.utcnow()
        self._track_memory = False
        self._core = CoreMetricsRegistry.get_instance()
        self.process = psutil.Process()
        self._background_task: Optional[asyncio.Task] = None

    @classmethod
    async def get_instance(cls) -> "MetricsRegistry":
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def get_instance_sync(cls) -> "MetricsRegistry":
        """Get singleton instance synchronously (for decorators)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def enable(self, track_memory: bool = True):
        """Enable metrics collection."""
        self.enabled = True
        self._track_memory = track_memory
        self._core.enable()

        if track_memory:
            tracemalloc.start()

        self._core.counter("http_requests_total", "Total HTTP requests")
        self._core.histogram("http_request_duration_seconds", "HTTP request duration")
        self._core.counter("component_calls_total", "Total component method calls")
        self._core.histogram("component_duration_seconds", "Component method duration")
        self._core.gauge("system_memory_bytes", "System memory usage in bytes")
        self._core.gauge("system_cpu_percent", "System CPU usage percent")

        try:
            loop = asyncio.get_running_loop()
            self._background_task = loop.create_task(self._collect_system_metrics())
        except RuntimeError:
            pass

    def disable(self):
        """Disable metrics collection."""
        self.enabled = False
        self._core.disable()
        if self._track_memory:
            tracemalloc.stop()
        if self._background_task:
            self._background_task.cancel()

    async def _collect_system_metrics(self):
        """Background task to collect system metrics."""
        while self.enabled:
            try:
                mem_info = self.process.memory_info()
                self._core.gauge("system_memory_bytes").set(
                    mem_info.rss, {"type": "rss"}
                )
                self._core.gauge("system_memory_bytes").set(
                    mem_info.vms, {"type": "vms"}
                )

                cpu_percent = self.process.cpu_percent(interval=None)
                self._core.gauge("system_cpu_percent").set(cpu_percent)

                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def record_http_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_sec: float,
    ):
        """Record HTTP request metrics."""
        if not self.enabled:
            return

        status = str(status_code)
        self._core.counter("http_requests_total").inc(
            {"method": method, "path": path, "status": status}
        )
        self._core.histogram("http_request_duration_seconds").observe(
            duration_sec, {"method": method, "path": path}
        )

    def record_component_call(
        self, component_name: str, duration_sec: float, error: bool = False
    ):
        """Record a component method call."""
        if not self.enabled:
            return

        status = "failure" if error else "success"
        self._core.counter("component_calls_total").inc(
            {"component": component_name, "status": status}
        )
        self._core.histogram("component_duration_seconds").observe(
            duration_sec, {"component": component_name}
        )


def Instrumented(enabled: bool = True):
    """
    Decorator to enable instrumentation on components.

    When applied to @Application, automatically instruments all components
    (services, repositories, controllers) in the application.

    When applied to individual components (@Service, @Repository, @RestController),
    instruments only that specific component.

    Args:
        enabled: Whether to enable instrumentation

    Example:
        # Option 1: Instrument entire application
        @Instrumented()
        @Application
        class App:
            pass

        # Option 2: Instrument specific component
        @Instrumented()
        @Service
        class UserService:
            async def get_user(self, user_id: int):
                # Automatically tracked
                return await self.user_repo.find_by_id(user_id)
    """

    def decorator(cls):
        # Store instrumentation config on the class
        cls._instrumented = enabled
        cls._instrumented_decorator_applied = True

        if not enabled:
            return cls

        # Check if this is an @Application class
        if hasattr(cls, "__mitsuki_application__"):
            # Mark for global instrumentation
            cls._instrument_all_components = True
            return cls

        # For individual components, apply instrumentation immediately
        _apply_instrumentation(cls)

        return cls

    return decorator


def _apply_instrumentation(cls):
    """Apply instrumentation to a component class."""

    component_name = cls.__name__

    for attr_name in dir(cls):
        if attr_name.startswith("_"):
            continue

        attr = getattr(cls, attr_name)
        if not callable(attr):
            continue

        if asyncio.iscoroutinefunction(attr):
            setattr(cls, attr_name, _wrap_async_method(component_name, attr))
        else:
            setattr(cls, attr_name, _wrap_sync_method(component_name, attr))


def should_instrument_component(component_cls, app_class=None) -> bool:
    """
    Check if a component should be instrumented.

    Returns True if:
    - Component has @Instrumented decorator with enabled=True, OR
    - Application has @Instrumented decorator and component doesn't explicitly disable it
    """
    # Check if component explicitly has @Instrumented
    if hasattr(component_cls, "_instrumented_decorator_applied"):
        return getattr(component_cls, "_instrumented", False)

    # Check if application has global instrumentation enabled
    if app_class and hasattr(app_class, "_instrument_all_components"):
        return getattr(app_class, "_instrument_all_components", False)

    return False


def _get_component_type(cls) -> str:
    """Determine component type from class decorators."""
    if hasattr(cls, "__mitsuki_service__"):
        return "service"
    elif hasattr(cls, "__mitsuki_repository__"):
        return "repository"
    elif hasattr(cls, "__mitsuki_rest_controller__"):
        return "controller"
    else:
        return "component"


def _wrap_async_method(component_name: str, method: Callable):
    """Wrap an async method with instrumentation."""

    @functools.wraps(method)
    async def wrapper(*args, **kwargs):
        registry = MetricsRegistry.get_instance_sync()
        if not registry.enabled:
            return await method(*args, **kwargs)

        start_time = time.perf_counter()
        error_occurred = False
        try:
            result = await method(*args, **kwargs)
            return result
        except Exception as e:
            error_occurred = True
            raise
        finally:
            duration_sec = time.perf_counter() - start_time
            registry.record_component_call(component_name, duration_sec, error_occurred)

    return wrapper


def _wrap_sync_method(component_name: str, method: Callable):
    """Wrap a sync method with instrumentation."""

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        registry = MetricsRegistry.get_instance_sync()
        if not registry.enabled:
            return method(*args, **kwargs)

        start_time = time.perf_counter()
        error_occurred = False
        try:
            result = method(*args, **kwargs)
            return result
        except Exception as e:
            error_occurred = True
            raise
        finally:
            duration_sec = time.perf_counter() - start_time
            registry.record_component_call(component_name, duration_sec, error_occurred)

    return wrapper


class InstrumentationMiddleware:
    """
    ASGI middleware to track HTTP requests.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        registry = MetricsRegistry.get_instance_sync()
        if not registry.enabled:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        start_time = time.perf_counter()

        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_sec = time.perf_counter() - start_time
            registry.record_http_request(method, path, status_code, duration_sec)


@Provider
class InstrumentationProvider:
    """
    Provider for instrumentation functionality.
    Automatically registered when instrumentation is enabled.
    """

    def __init__(self):
        self.registry = MetricsRegistry.get_instance_sync()
        self._core = CoreMetricsRegistry.get_instance()

    def record_metric(
        self, metric_name: str, value: float, labels: Optional[dict[str, str]] = None
    ):
        """
        Record a custom counter metric.

        Example:
            self.instrumentation.record_metric(
                metric_name="user_registrations",
                value=1,
                labels={"source": "web"}
            )
        """
        if self.registry.enabled:
            counter = self._core.counter(metric_name, f"Custom metric: {metric_name}")
            counter.inc(labels, value)
