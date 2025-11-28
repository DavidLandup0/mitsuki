import asyncio
from typing import Any, Dict, List, Optional, Type

from mitsuki.config.properties import get_config, log_config_sources
from mitsuki.core.container import get_container
from mitsuki.core.enums import Scope, ServerType
from mitsuki.core.logging import configure_logging, get_logger
from mitsuki.core.metrics import create_metrics_endpoint
from mitsuki.core.providers import initialize_configuration_providers
from mitsuki.core.scanner import scan_components
from mitsuki.core.scheduler import get_scheduler
from mitsuki.core.server import (
    _start_granian,
    _start_socketify,
    _start_uvicorn,
    create_server,
)
from mitsuki.data import initialize_database
from mitsuki.openapi import register_openapi_endpoints
from mitsuki.web.controllers import get_all_controllers


class ApplicationContext:
    """
    Application context that manages the lifecycle of components.
    Handles component scanning, initialization, and server startup.
    """

    def __init__(
        self, application_class: Type, config: Optional[Dict[str, Any]] = None
    ):
        self.application_class = application_class
        self.config = config or {}
        self.container = get_container()
        self.controllers: List[Any] = []
        self._server = None
        self._scheduler = None
        self._setup_logging()

    def _setup_logging(self):
        config = get_config()

        log_level = config.get("logging.level")
        log_format = config.get("logging.format")
        sqlalchemy_logging = config.get_bool("logging.sqlalchemy")

        # Check for custom logging providers
        custom_formatter = None
        custom_handlers = None

        if self.container.has_by_name("log_formatter"):
            custom_formatter = self.container.get_by_name("log_formatter")

        if self.container.has_by_name("log_handlers"):
            custom_handlers = self.container.get_by_name("log_handlers")

        configure_logging(
            level=log_level,
            format=log_format,
            sqlalchemy=sqlalchemy_logging,
            custom_formatter=custom_formatter,
            custom_handlers=custom_handlers,
        )

    def _register_metrics_endpoint(self):
        """Register metrics endpoint if enabled in configuration."""

        config = get_config()
        metrics_controller = create_metrics_endpoint(config)

        if metrics_controller:
            # Metrics controller is auto-registered via @RestController decorator
            pass

    def _scan_scheduled_tasks(self):
        """Scan all registered components for @Scheduled methods."""
        logger = get_logger()
        config = get_config()
        scheduler_enabled = config.get_bool("scheduler.enabled")

        if not scheduler_enabled:
            logger.debug("Scheduler is disabled")
            return

        scheduler = get_scheduler()
        logger.debug(
            f"Scanning for scheduled tasks in {len(self.container._components_by_name)} components"
        )

        # Get all registered components from the container by name
        for component_name in list(self.container._components_by_name.keys()):
            try:
                component = self.container.get_by_name(component_name)

                # Scan all methods of the component
                for attr_name in dir(component):
                    if attr_name.startswith("_"):
                        continue

                    try:
                        attr = getattr(component, attr_name)
                        if callable(attr) and hasattr(attr, "__mitsuki_scheduled__"):
                            config = attr.__mitsuki_schedule_config__
                            logger.debug(
                                f"Found scheduled method: {component_name}.{attr_name}"
                            )
                            scheduler.register_scheduled_method(component, attr, config)
                    except Exception as e:
                        # Skip attributes that can't be accessed
                        logger.debug(
                            f"Could not access {component_name}.{attr_name}: {e}"
                        )
                        continue

            except Exception as e:
                # Skip components that can't be instantiated
                logger.debug(f"Could not instantiate {component_name}: {e}")
                continue

    def start(self, host: str = "127.0.0.1", port: int = 8000):
        asyncio.run(initialize_database())
        self.controllers = get_all_controllers()

        # Register metrics endpoint if enabled
        self._register_metrics_endpoint()

        # Register OpenAPI documentation endpoints if enabled
        config = get_config()
        register_openapi_endpoints(self, config)

        # Note: Scheduled tasks are scanned in the worker process (see server.py _lifespan)
        # This ensures tasks are registered in the correct process when using multi-process servers

        server = create_server(self)
        self._server = server

        config = get_config()
        logger = get_logger()

        # To avoid circular imports
        from mitsuki import __version__

        logger.info("")
        logger.info("    ♡ ｡ ₊°༺❤︎༻°₊ ｡ ♡")
        logger.info("              _ __             __   _")
        logger.info("   ____ ___  (_) /________  __/ /__(_)")
        logger.info("  / __ `__ \\/ / __/ ___/ / / / //_/ /")
        logger.info(" / / / / / / / /_(__  ) /_/ / ,< / /")
        logger.info("/_/ /_/ /_/_/\\__/____/\\__,_/_/|_/_/")
        logger.info("    °❀˖ ° °❀⋆.ೃ࿔*:･  ° ❀˖°")
        logger.info("")
        logger.info(f":: Mitsuki ::                (v{__version__})")
        logger.info("")

        # Log configuration sources if enabled
        if config.get_bool("logging.log_config_sources"):
            log_config_sources(config, logger, max_cols=3)

        logger.info(f"Mitsuki application starting on http://{host}:{port}")

        log_level_str = config.get("logging.level").lower()
        server_type = config.get("server.type").lower()
        workers = config.get("server.workers")
        access_log = config.get_bool("server.access_log")

        if server_type == ServerType.GRANIAN:
            _start_granian(
                self.application_class, host, port, workers, log_level_str, access_log
            )
        elif server_type == ServerType.SOCKETIFY:
            _start_socketify(server, host, port, workers, log_level_str, access_log)
        else:
            _start_uvicorn(server, host, port, log_level_str, access_log)


def Application(
    cls: Optional[Type] = None, *, scan_packages: Optional[List[str]] = None
) -> Type:
    """
    Main application decorator.
    Marks a class as the entry point for a Mitsuki application.

    Usage:
        @Application
        class MyApp:
            pass

        @Application(scan_packages=["app.controllers", "app.services"])
        class MyApp:
            pass

    Args:
        scan_packages: Optional list of package names to scan for components.
                      If not provided, scans the application directory recursively.
    """

    def decorator(cls: Type) -> Type:
        cls.__mitsuki_application__ = True
        cls.__mitsuki_configuration__ = True
        cls.__mitsuki_scan_packages__ = scan_packages

        # Register as configuration component
        container = get_container()
        container.register(cls, name=cls.__name__, scope=Scope.SINGLETON)

        # Attach factory and ASGI wrapper for Granian workers
        _app_instance = None
        _init_task = None

        async def __mitsuki_create_app_async__():
            """Async factory function that creates the ASGI app for Granian workers."""
            nonlocal _app_instance
            if _app_instance is None:
                context = ApplicationContext(cls)
                scan_components(cls, scan_packages=scan_packages)
                initialize_configuration_providers()
                await initialize_database()
                context._register_metrics_endpoint()
                context.controllers = get_all_controllers()

                # Register OpenAPI documentation endpoints if enabled
                config = get_config()
                register_openapi_endpoints(context, config)

                # Note: Scheduled tasks are scanned in server.py _lifespan() after container repopulation
                _app_instance = create_server(context)
            return _app_instance

        # ASGI wrapper that Granian workers will import
        # This gets called on first request in each worker to create the app
        async def __mitsuki_app__(scope, receive, send):
            nonlocal _init_task
            # Ensure app is initialized before handling requests
            if _app_instance is None:
                if _init_task is None:
                    _init_task = asyncio.create_task(__mitsuki_create_app_async__())
                app = await _init_task
            else:
                app = _app_instance
            await app(scope, receive, send)

        cls.__mitsuki_create_app__ = staticmethod(__mitsuki_create_app_async__)
        cls.__mitsuki_app__ = staticmethod(__mitsuki_app__)

        @classmethod
        def run(cls, host: Optional[str] = None, port: Optional[int] = None):
            """Run the application."""
            # Create application context
            context = ApplicationContext(cls)

            # Scan for components
            scan_components(cls, scan_packages=scan_packages)

            # Initialize configuration and providers
            initialize_configuration_providers()

            config = get_config()

            # Resolve host (priority: argument > class attribute > config)
            if host is None and hasattr(cls, "host"):
                app_instance = context.container.get(cls)
                host = getattr(app_instance, "host", None)
            if host is None:
                host = config.get("server.host")

            # Resolve port (priority: argument > class attribute > config)
            if port is None and hasattr(cls, "port"):
                app_instance = context.container.get(cls)
                port = getattr(app_instance, "port", None)
            if port is None:
                port = config.get("server.port")

            # Start the server
            context.start(host=host, port=port)

        cls.run = run
        cls._context = None

        return cls

    # Support both @Application and @Application()
    if cls is None:
        # Called with arguments: @Application(scan_packages=[...])
        return decorator
    else:
        # Called without arguments: @Application
        return decorator(cls)
