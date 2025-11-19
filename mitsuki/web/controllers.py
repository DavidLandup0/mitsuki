from typing import List, Tuple, Type

from mitsuki.core.container import get_container
from mitsuki.core.enums import Scope


def RestController(path: str = ""):
    """
    REST controller decorator.
    Marks a class as a web controller that handles HTTP requests.

    Args:
        path: Base path for all routes in this controller
    """

    def decorator(cls: Type) -> Type:
        container = get_container()
        container.register(cls, name=cls.__name__, scope=Scope.SINGLETON)

        cls.__mitsuki_controller__ = True
        cls.__mitsuki_rest_controller__ = True
        cls.__mitsuki_base_path__ = path
        cls.__mitsuki_component__ = True
        cls.__mitsuki_name__ = cls.__name__
        cls.__mitsuki_scope__ = Scope.SINGLETON

        return cls

    return decorator


def Controller(path: str = ""):
    """
    Controller decorator - alias for @RestController.
    Marks a class as a web controller that handles HTTP requests.

    Args:
        path: Base path for all routes in this controller
    """
    return RestController(path)


def Router(path: str = ""):
    """
    Router decorator - alias for @RestController.
    Marks a class as a web controller that handles HTTP requests.

    Args:
        path: Base path for all routes in this router
    """
    return RestController(path)


def RestRouter(path: str = ""):
    """
    REST router decorator - alias for @RestController.
    Automatically serializes return values to JSON.

    Args:
        path: Base path for all routes in this router
    """
    return RestController(path)


def get_all_controllers() -> List[Tuple[Type, str]]:
    """
    Get all registered controllers from the container.
    Returns list of (controller_class, base_path) tuples.
    """
    container = get_container()
    controllers = []

    for component_name in container._components_by_name.keys():
        metadata = container._components_by_name[component_name]
        cls = metadata.cls

        if hasattr(cls, "__mitsuki_controller__"):
            base_path = getattr(cls, "__mitsuki_base_path__", "")
            controllers.append((cls, base_path))

    return controllers
