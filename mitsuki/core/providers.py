import inspect

from mitsuki.core.container import get_container
from mitsuki.core.enums import Scope


def initialize_configuration_providers():
    """
    Process all @Configuration classes and instantiate @Provider methods.
    Respects @Profile annotations for conditional provider registration.
    """
    container = get_container()

    # Get all registered @Configuration classes
    config_classes = container.get_all_configurations()

    for config_metadata in config_classes:
        # Skip if profile is inactive
        if hasattr(config_metadata.cls, "__mitsuki_profile_active__"):
            if not config_metadata.cls.__mitsuki_profile_active__:
                continue

        # Get or create configuration instance
        config_instance = container.get(config_metadata.cls)

        # Find all @Provider methods
        for name, method in inspect.getmembers(
            config_instance, predicate=inspect.ismethod
        ):
            if hasattr(method, "__mitsuki_provider__"):
                # Skip if provider has @Profile and profile is inactive
                if hasattr(method, "__mitsuki_profile_active__"):
                    if not method.__mitsuki_profile_active__:
                        continue

                provider_name = method.__mitsuki_provider_name__
                provider_scope = method.__mitsuki_provider_scope__

                # Execute the provider factory method
                provider_instance = method()

                # Create a unique wrapper class for this provider to avoid type collisions
                # (multiple providers might return the same type like str, int, etc.)
                provider_wrapper_class = type(
                    f"__Provider_{provider_name}",
                    (),
                    {
                        "__provider_instance__": provider_instance,
                        "__provider_factory__": method,
                    },
                )

                # Register the wrapper class in the container
                container.register(
                    provider_wrapper_class, name=provider_name, scope=provider_scope
                )

                # Store the provider instance (not the wrapper) if singleton
                if provider_scope == Scope.SINGLETON:
                    metadata = container._components[provider_wrapper_class]
                    metadata.instance = provider_instance
