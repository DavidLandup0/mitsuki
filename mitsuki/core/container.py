import inspect
import logging
import sys
import threading
from typing import Any, Dict, Optional, Set, Type, Union, get_type_hints

from mitsuki.core.enums import Scope
from mitsuki.exceptions import (
    CircularDependencyException,
    ComponentNotFoundException,
    DependencyInjectionException,
)


class ComponentMetadata:
    """Metadata about a registered component."""

    def __init__(
        self, cls: Type, name: str, scope: Union[Scope, str] = Scope.SINGLETON
    ):
        self.cls = cls
        self.name = name
        self.scope = Scope.from_string(scope) if isinstance(scope, str) else scope
        self.instance: Optional[Any] = None
        self.dependencies: Set[Type] = set()
        self.is_configuration: bool = False


class DIContainer:
    """
    Dependency Injection container with automatic constructor injection.
    Supports singleton and prototype scopes.
    """

    def __init__(self):
        self._components: Dict[Type, ComponentMetadata] = {}
        self._components_by_name: Dict[str, ComponentMetadata] = {}
        self._resolving = threading.local()  # Thread-local circular dependency tracking
        self._lock = threading.RLock()  # Reentrant lock for nested get() calls

    def register(
        self,
        cls: Type,
        name: Optional[str] = None,
        scope: Union[Scope, str] = Scope.SINGLETON,
    ):
        """Register a component class with the container."""
        component_name = name or cls.__name__
        metadata = ComponentMetadata(cls, component_name, scope)

        # Mark if this is a configuration class
        if hasattr(cls, "__mitsuki_configuration__"):
            metadata.is_configuration = True

        # Analyze constructor dependencies
        sig = inspect.signature(cls.__init__)
        type_hints = get_type_hints(cls.__init__)

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Get type from annotation
            param_type = type_hints.get(param_name)
            if param_type:
                metadata.dependencies.add(param_type)

        self._components[cls] = metadata
        self._components_by_name[component_name] = metadata

    def get(self, cls: Type) -> Any:
        """Resolve and return an instance of the requested component."""
        if cls not in self._components:
            raise ComponentNotFoundException(
                f"Component {cls.__name__} not registered in container"
            )

        metadata = self._components[cls]

        # For provider wrappers, return the stored instance directly
        if hasattr(cls, "__provider_instance__"):
            return (
                metadata.instance
                if metadata.instance is not None
                else cls.__provider_instance__
            )

        # Singleton: double-check with lock
        if metadata.scope == Scope.SINGLETON:
            if metadata.instance is not None:
                return metadata.instance

            with self._lock:
                if metadata.instance is not None:
                    return metadata.instance

                # Check for circular dependencies
                resolving_set = getattr(self._resolving, "stack", None)
                if resolving_set is None:
                    resolving_set = set()
                    self._resolving.stack = resolving_set

                if cls in resolving_set:
                    raise CircularDependencyException(
                        f"Circular dependency detected for {cls.__name__}"
                    )

                resolving_set.add(cls)
                try:
                    instance = self._create_instance(cls, metadata)
                    metadata.instance = instance
                    return instance
                finally:
                    resolving_set.discard(cls)

        # Prototype: no caching
        resolving_set = getattr(self._resolving, "stack", None)
        if resolving_set is None:
            resolving_set = set()
            self._resolving.stack = resolving_set

        if cls in resolving_set:
            raise CircularDependencyException(
                f"Circular dependency detected for {cls.__name__}"
            )

        resolving_set.add(cls)
        try:
            return self._create_instance(cls, metadata)
        finally:
            resolving_set.discard(cls)

    def _create_instance(self, cls: Type, metadata: ComponentMetadata) -> Any:
        """Create instance with dependency resolution."""
        # Resolve dependencies
        dependencies = {}
        sig = inspect.signature(cls.__init__)
        type_hints = get_type_hints(cls.__init__)

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_type = type_hints.get(param_name)
            if param_type:
                # Try to resolve by type first
                if param_type in self._components:
                    dependencies[param_name] = self.get(param_type)
                # Fall back to resolution by name (for providers from factory methods)
                elif param_name in self._components_by_name:
                    dependencies[param_name] = self.get_by_name(param_name)
                else:
                    raise DependencyInjectionException(
                        f"Cannot resolve dependency '{param_name}' of type '{param_type.__name__}' "
                        f"for {cls.__name__}. No provider found by type or by name."
                    )

        # Create instance with resolved dependencies
        return cls(**dependencies)

    def get_by_name(self, name: str) -> Any:
        """Resolve component by name."""
        if name not in self._components_by_name:
            raise ComponentNotFoundException(
                f"Component '{name}' not registered in container"
            )

        metadata = self._components_by_name[name]
        return self.get(metadata.cls)

    def has(self, cls: Type) -> bool:
        """Check if a component is registered."""
        return cls in self._components

    def has_by_name(self, name: str) -> bool:
        """Check if a component is registered by name."""
        return name in self._components_by_name

    def get_all_configurations(self) -> list:
        """Get all registered @Configuration classes."""
        return [
            metadata
            for metadata in self._components.values()
            if metadata.is_configuration
        ]

    def clear(self):
        """Clear all registered components."""
        self._components.clear()
        self._components_by_name.clear()
        self._resolving.clear()


# Global container instance
_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get the global DI container instance."""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def populate_container_from_decorators():
    """
    Populate the container from already-decorated classes.
    Scans sys.modules for classes with decorator metadata and registers them.
    """
    container = get_container()
    logger = logging.getLogger(__name__)

    registered_count = 0
    modules_scanned = 0
    classes_with_metadata = []

    for module_name, module in list(sys.modules.items()):
        if not module or module_name.startswith("_"):
            continue

        try:
            classes_found = 0
            for name, obj in inspect.getmembers(module, inspect.isclass):
                classes_found += 1

                # Log if this class has component metadata
                if hasattr(obj, "__mitsuki_component__"):
                    classes_with_metadata.append(f"{module_name}.{obj.__name__}")
                    logger.debug(f"Found decorated class: {module_name}.{obj.__name__}")

                # Check for component/service decorator
                if hasattr(obj, "__mitsuki_component__"):
                    scope = getattr(obj, "__mitsuki_scope__", Scope.SINGLETON)
                    component_name = (
                        getattr(obj, "__mitsuki_name__", None) or obj.__name__
                    )

                    # Skip if already registered by name (not by class reference)
                    # In spawn mode, same class can have different identities
                    if container.has_by_name(component_name):
                        logger.debug(
                            f"Skipping {obj.__name__} - already registered by name '{component_name}'"
                        )
                        continue

                    container.register(obj, name=component_name, scope=scope)
                    registered_count += 1
                    logger.debug(
                        f"Re-registered {obj.__name__} from {module_name} in worker container"
                    )

            if classes_found > 0:
                modules_scanned += 1

        except Exception as e:
            # Skip modules that can't be inspected
            logger.debug(f"Couldn't inspect module {module_name}: {e}")

    logger.info(
        f"Scanned {modules_scanned} modules, found {len(classes_with_metadata)} classes with metadata, populated container with {registered_count} components"
    )
    if classes_with_metadata:
        logger.debug(f"Classes with metadata: {classes_with_metadata}")
    return registered_count


def set_container(container: DIContainer):
    """Set the global DI container instance."""
    global _container
    _container = container
