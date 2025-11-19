import inspect
import logging
from contextlib import asynccontextmanager
from typing import List

import uvicorn
from granian import Granian
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from mitsuki.config.properties import get_config
from mitsuki.core.logging import get_granian_log_config
from mitsuki.core.scheduler import get_scheduler
from mitsuki.data.repository import get_database_adapter
from mitsuki.exceptions import DataException
from mitsuki.web.parameter_binder import ParameterBinder
from mitsuki.web.response_processor import ResponseProcessor
from mitsuki.web.route_builder import RouteBuilder


class MitsukiASGIApp:
    """
    ASGI application that handles routing and request processing.
    Translates Mitsuki's @RestController/@GetMapping decorators to HTTP routes.
    """

    def __init__(self, context):
        self.context = context

        # Load configuration once
        config = get_config()
        max_body_size = config.get("server.max_body_size")
        max_file_size = config.get("server.multipart.max_file_size")
        max_request_size = config.get("server.multipart.max_request_size")
        self.cors_enabled = config.get_bool("server.cors.enabled")
        self.cors_origins = config.get("server.cors.allowed_origins")
        debug_mode = config.get_bool("debug", default=False)
        ignore_trailing_slash = config.get_bool("server.ignore_trailing_slash")

        # Initialize components
        parameter_binder = ParameterBinder(
            max_body_size, max_file_size, max_request_size
        )
        response_processor = ResponseProcessor()
        route_builder = RouteBuilder(
            context,
            parameter_binder,
            response_processor,
            ignore_trailing_slash,
            debug_mode,
        )

        # Build routes from Mitsuki controllers
        routes = route_builder.build_routes()

        # Build middleware stack
        middleware = self._build_middleware()

        # Create ASGI app with lifespan context manager
        self.app = Starlette(
            routes=routes,
            middleware=middleware,
            lifespan=self._lifespan,
        )

    @asynccontextmanager
    async def _lifespan(self, app):
        """Lifespan context manager for startup/shutdown."""

        # Note: Container is already populated when decorators run during module import.
        # Thus, it's not being managed here - it's a pre-lifespan component.

        # Scan and register scheduled tasks
        # These are registered as tasks, not components, hence
        # not in the container at startup.
        self.context._scan_scheduled_tasks()

        scheduler = get_scheduler()
        await scheduler.start()

        yield

        # Shutdown
        # Stop scheduler
        await scheduler.stop()

        # Disconnect database
        try:
            adapter = get_database_adapter()
            await adapter.disconnect()
            logging.info("Database disconnected")
        except (RuntimeError, DataException):
            # Database not initialized - this is fine
            # TODO: Add message for if adapter.disconnect()
            # throws an exception.
            pass

    def _build_middleware(self) -> List[Middleware]:
        """Build middleware stack."""
        middleware = []

        # CORS middleware
        if self.cors_enabled:
            middleware.append(
                Middleware(
                    CORSMiddleware,
                    allow_origins=self.cors_origins,
                    allow_credentials=True,
                    allow_methods=["*"],
                    allow_headers=["*"],
                )
            )

        return middleware

    async def __call__(self, scope, receive, send):
        """ASGI interface - delegate to internal app."""
        await self.app(scope, receive, send)


def create_server(context):
    """Create ASGI application from application context."""
    return MitsukiASGIApp(context)


def _start_uvicorn(server, host: str, port: int, log_level: str, access_log: bool):
    """Start server using uvicorn."""
    # Get logging configuration
    config = get_config()
    log_format = config.get("logging.format")
    timeout = config.get("server.timeout")

    # Create uvicorn log config that uses our colored formatter
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "colored": {
                "()": "mitsuki.core.logging.ColoredFormatter",
                "format": log_format,
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "colored",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "class": "logging.StreamHandler",
                "formatter": "colored",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": log_level.upper(),
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": log_level.upper(),
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": log_level.upper(),
                "propagate": False,
            },
        },
    }

    kwargs = {
        "host": host,
        "port": port,
        "log_level": log_level,
        "access_log": access_log,
        "log_config": log_config,
    }

    if timeout is not None:
        kwargs["timeout_keep_alive"] = timeout

    uvicorn.run(server, **kwargs)


def _start_granian(
    application_class,
    host: str,
    port: int,
    workers: int,
    log_level: str,
    access_log: bool,
):
    """Start server using Granian with factory pattern."""
    # Get the module where the application class is defined
    app_module = inspect.getmodule(application_class)
    module_name = app_module.__name__ if app_module else "__main__"
    class_name = application_class.__name__

    # Construct the target string for Granian
    # The __mitsuki_app__ wrapper was already attached by the @Application decorator
    target = f"{module_name}:{class_name}.__mitsuki_app__"

    # Get logging configuration
    config = get_config()
    log_format = config.get("logging.format")
    log_dictconfig = get_granian_log_config(level=log_level, format=log_format)
    timeout = config.get("server.timeout")

    kwargs = {
        "target": target,
        "address": host,
        "port": port,
        "interface": "asgi",
        "workers": workers,
        "log_dictconfig": log_dictconfig,
        "log_access": access_log,
    }

    if timeout is not None:
        kwargs["http1_keep_alive"] = timeout

    granian_server = Granian(**kwargs)
    granian_server.serve()


def _start_socketify(
    server, host: str, port: int, workers: int, log_level: str, access_log: bool
):
    """Start server using socketify."""
    from socketify import ASGI, AppListenOptions

    # Create socketify ASGI wrapper with performance tuning
    asgi_app = ASGI(
        server,
        lifespan=True,
        task_factory_max_items=0,  # Unlimited task queue for better throughput
    )

    # Configure listen options
    options = AppListenOptions(port=port, host=host or "0.0.0.0")

    # Listen on port
    asgi_app.listen(
        options, lambda config: logging.info(f"Socketify listening on {host}:{port}")
    )

    # Run with workers
    asgi_app.run(workers=workers)
