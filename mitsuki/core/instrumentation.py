import asyncio
import functools
import importlib.util
import inspect
import time
import tracemalloc
from types import FunctionType
from typing import Callable, Dict, Optional, Set, Type

from starlette.routing import Route

from mitsuki.core.decorators import Component, _instrumentable_components
from mitsuki.core.metrics_core import (
    MetricsStorage,
    validate_label_names,
    validate_metric_name,
)

# Set by @Instrumented: True opts in, False opts out. On the @Application
# class it opts in every component.
_MARKER = "_instrumented_decorator_applied"

# Guards against wrapping a class more than once.
_APPLIED = "_instrumentation_applied"

# Set on every instrumentation wrapper, so a subclass inheriting one from an
# instrumented parent does not wrap it again and record each call twice.
_WRAPPER = "__mitsuki_instrumented__"


@Component()
class InstrumentationRegistry:
    """
    Collects HTTP, component and system metrics.

    Metrics are recorded only while enabled. Process CPU and memory are sampled
    whenever instrumentation runs; track_memory additionally reports Python's
    traced memory, at the cost of tracemalloc overhead.
    """

    def __init__(self, metrics_storage: MetricsStorage):
        self.enabled: bool = False
        self._track_memory = False
        self._core = metrics_storage
        self.process = None
        self._background_task: Optional[asyncio.Task] = None

        self._requests = None
        self._request_duration = None
        self._component_calls = None
        self._component_duration = None

    def enable(self, track_memory: bool = False):
        """
        Begin recording metrics.

        Raises RuntimeError when psutil, provided by the mitsuki[metrics] extra,
        is not installed.
        """
        if importlib.util.find_spec("psutil") is None:
            raise RuntimeError(
                "instrumentation.enabled requires psutil: "
                "pip install 'mitsuki[metrics]'"
            )

        # psutil is an optional dependency, needed only once instrumentation
        # is enabled, so it is imported here rather than at module level.
        import psutil

        self.process = psutil.Process()
        self.enabled = True
        self._track_memory = track_memory

        self._requests = self._core.counter(
            "http_requests_total", "Total HTTP requests"
        )
        self._request_duration = self._core.histogram(
            "http_request_duration_seconds", "HTTP request duration"
        )
        self._component_calls = self._core.counter(
            "component_calls_total", "Total component method calls"
        )
        self._component_duration = self._core.histogram(
            "component_duration_seconds", "Component method duration"
        )

        # Process CPU and memory come from psutil and are cheap to sample.
        self._core.gauge("system_memory_bytes", "Process memory usage in bytes")
        self._core.gauge("system_cpu_percent", "Process CPU usage percent")

        # tracemalloc adds substantial allocation overhead, so traced memory is
        # opt-in through track_memory.
        if track_memory:
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            self._core.gauge(
                "system_traced_memory_bytes", "Python traced memory in bytes"
            )

    def disable(self):
        """Stop recording metrics."""
        self.enabled = False
        if self._track_memory and tracemalloc.is_tracing():
            tracemalloc.stop()
        self.stop_background_collection()

    def start_background_collection(self):
        """Start sampling system metrics."""
        if self._background_task or not self.enabled:
            return
        self._background_task = asyncio.get_running_loop().create_task(
            self._collect_system_metrics()
        )

    def stop_background_collection(self):
        """Cancel the system metrics sampler."""
        if self._background_task:
            self._background_task.cancel()
            self._background_task = None

    def _sample_once(self):
        """Sample process CPU and memory, plus traced memory when enabled."""
        mem_info = self.process.memory_info()
        memory = self._core.gauge("system_memory_bytes")
        memory.set(mem_info.rss, {"type": "rss"})
        memory.set(mem_info.vms, {"type": "vms"})
        self._core.gauge("system_cpu_percent").set(
            self.process.cpu_percent(interval=None)
        )

        if self._track_memory:
            current, peak = tracemalloc.get_traced_memory()
            traced = self._core.gauge("system_traced_memory_bytes")
            traced.set(current, {"type": "current"})
            traced.set(peak, {"type": "peak"})

    async def _collect_system_metrics(self):
        """Sample system metrics every 5 seconds while enabled."""
        while self.enabled:
            self._sample_once()
            await asyncio.sleep(5)

    def record_http_request(
        self, method: str, route: str, status_code: int, duration_sec: float
    ):
        """Record one HTTP request against its matched route template."""
        if not self.enabled:
            return

        # Keys built pre-sorted by label name (method < path < status) to match
        # _labels_to_key without allocating and sorting a dict per request.
        self._requests.inc_key(
            (("method", method), ("path", route), ("status", str(status_code)))
        )
        self._request_duration.observe_key(
            duration_sec, (("method", method), ("path", route))
        )

    def record_component_call(
        self,
        component_name: str,
        method_name: str,
        duration_sec: float,
        error: bool = False,
    ):
        """Record one component method call."""
        if not self.enabled:
            return

        # Keys built pre-sorted by label name (component < method < status).
        status = "failure" if error else "success"
        self._component_calls.inc_key(
            (("component", component_name), ("method", method_name), ("status", status))
        )
        self._component_duration.observe_key(
            duration_sec, (("component", component_name), ("method", method_name))
        )


def Instrumented(enabled: bool = True):
    """
    Mark an application or component for instrumentation.

    On an @Application class, instruments every @Service, @Repository and
    @RestController. On a single component, instruments only that component.
    enabled=False opts a component out of application-wide instrumentation.

    Instrumentation is applied at startup and only when
    instrumentation.enabled is set in configuration. Order relative to
    @Application and the stereotype decorators does not matter.

        @Instrumented()
        @Application
        class App:
            pass

        @Instrumented()
        @Service()
        class UserService:
            async def get_user(self, user_id: int):
                return await self.user_repo.find_by_id(user_id)
    """

    def decorator(cls):
        setattr(cls, _MARKER, enabled)
        return cls

    return decorator


def apply_instrumentation(app_cls: Type, registry: InstrumentationRegistry):
    """
    Instrument every component that has opted in.

    A component opts in through @Instrumented on itself, or through
    @Instrumented on the application class. @Instrumented(enabled=False) on a
    component always wins.
    """
    instrument_all = app_cls.__dict__.get(_MARKER) is True

    for cls in _instrumentable_components:
        if cls.__dict__.get(_APPLIED):
            continue

        opted_in = cls.__dict__.get(_MARKER)
        if opted_in is False:
            continue
        if opted_in or instrument_all:
            _instrument_class(cls, registry)


def _instrument_class(cls: Type, registry: InstrumentationRegistry):
    """
    Wrap the public methods a component defines or inherits.

    Methods inherited already wrapped, from an instrumented parent, are left
    as they are: wrappers attribute each call to the class of the instance
    called, so the parent's wrapper already records calls on this class.
    """
    setattr(cls, _APPLIED, True)
    seen = set()

    for klass in cls.__mro__:
        if klass is object:
            continue

        for name, attr in list(vars(klass).items()):
            if name.startswith("_") or name in seen:
                continue

            seen.add(name)

            # staticmethod, classmethod and property are descriptors; rebinding
            # them as plain functions changes how they resolve on instances.
            if not isinstance(attr, FunctionType) or attr.__dict__.get(_WRAPPER):
                continue

            setattr(cls, name, _instrument_function(attr, registry))


def _instrument_function(method: Callable, registry: InstrumentationRegistry):
    """
    Wrap a method to record its call count and duration.

    The component label is the class of the instance called, so a method
    shared through inheritance is attributed to the concrete component.
    """
    record = registry.record_component_call
    method_name = method.__name__

    if inspect.iscoroutinefunction(method):

        @functools.wraps(method)
        async def async_wrapper(self, *args, **kwargs):
            start_time = time.perf_counter()
            failed = False
            try:
                return await method(self, *args, **kwargs)
            except Exception:
                failed = True
                raise
            finally:
                record(
                    type(self).__name__,
                    method_name,
                    time.perf_counter() - start_time,
                    failed,
                )

        setattr(async_wrapper, _WRAPPER, True)
        return async_wrapper

    @functools.wraps(method)
    def sync_wrapper(self, *args, **kwargs):
        start_time = time.perf_counter()
        failed = False
        try:
            return method(self, *args, **kwargs)
        except Exception:
            failed = True
            raise
        finally:
            record(
                type(self).__name__,
                method_name,
                time.perf_counter() - start_time,
                failed,
            )

    setattr(sync_wrapper, _WRAPPER, True)
    return sync_wrapper


def build_route_map(routes) -> Dict:
    """
    Map route endpoints to their path templates.

    A trailing-slash alias shares its canonical route's endpoint, so when an
    endpoint serves several templates the shortest, canonical one is kept.
    """
    mapping = {}
    for route in routes:
        if not isinstance(route, Route):
            continue

        existing = mapping.get(route.endpoint)
        if existing is None or len(route.path_format) < len(existing):
            mapping[route.endpoint] = route.path_format

    return mapping


class InstrumentationMiddleware:
    """
    ASGI middleware recording request counts and latency.

    Requests are labelled by matched route template rather than raw path, so
    metric cardinality stays bounded by the size of the route table. Requests
    matching a template in excluded are not recorded.
    """

    UNMATCHED = "<unmatched>"

    def __init__(
        self,
        app,
        registry: InstrumentationRegistry,
        routes: Dict,
        excluded: Set[str] = frozenset(),
    ):
        self.app = app
        self.registry = registry
        self.routes = routes
        self.excluded = excluded

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.registry.enabled:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        start_time = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Starlette's router writes the matched endpoint into the scope.
            route = self.routes.get(scope.get("endpoint"), self.UNMATCHED)
            if route not in self.excluded:
                self.registry.record_http_request(
                    method, route, status_code, time.perf_counter() - start_time
                )


@Component()
class InstrumentationProvider:
    """Records custom application metrics."""

    def __init__(self, metrics_storage: MetricsStorage):
        self._core = metrics_storage

    def record_metric(
        self, metric_name: str, value: float, labels: Optional[dict[str, str]] = None
    ):
        """
        Record a custom counter metric.

            self.instrumentation.record_metric(
                metric_name="user_registrations",
                value=1,
                labels={"source": "web"},
            )

        Raises ValueError for a metric or label name Prometheus cannot accept,
        or a metric name already registered as a gauge or histogram. Names are
        validated even while metrics are disabled, so a bad name surfaces before
        metrics are switched on.
        """
        validate_metric_name(metric_name)
        if labels:
            validate_label_names(labels)

        if not self._core.enabled:
            return

        counter = self._core.counter(metric_name, f"Custom metric: {metric_name}")
        counter.inc(labels, value)
