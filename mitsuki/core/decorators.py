from functools import wraps
from typing import Callable, Optional, Type, Union

from mitsuki.core.container import get_container
from mitsuki.core.enums import Scope


def Scheduled(
    fixed_rate: Optional[int] = None,
    fixed_delay: Optional[int] = None,
    cron: Optional[str] = None,
    initial_delay: int = 0,
    timezone: Optional[str] = None,
) -> Callable:
    """
    Mark a method to run on a schedule.

    Args:
        fixed_rate: Interval in milliseconds (run every N ms)
        fixed_delay: Delay in milliseconds after previous completion
        cron: Cron expression (e.g., "0 */5 * * * *" for every 5 minutes)
        initial_delay: Delay before first execution in milliseconds
        timezone: Timezone for cron expressions (e.g., "America/New_York")

    Example:
        @Service()
        class NotificationService:
            @Scheduled(fixed_rate=5000)  # Every 5 seconds
            async def send_notifications(self):
                await self.process_pending()

            @Scheduled(fixed_delay=10000)  # 10 seconds after completion
            async def cleanup(self):
                await self.cleanup_old_data()

            @Scheduled(cron="0 0 2 * * *")  # Every day at 2 AM
            async def daily_report(self):
                await self.generate_report()
    """
    if not any([fixed_rate, fixed_delay, cron]):
        raise ValueError(
            "Must specify at least one of: fixed_rate, fixed_delay, or cron"
        )

    def decorator(func: Callable) -> Callable:
        func.__mitsuki_scheduled__ = True
        func.__mitsuki_schedule_config__ = {
            "fixed_rate": fixed_rate,
            "fixed_delay": fixed_delay,
            "cron": cron,
            "initial_delay": initial_delay,
            "timezone": timezone,
        }
        return func

    return decorator


def Component(name: Optional[str] = None, scope: Union[str, Scope] = Scope.SINGLETON):
    """
    Generic component decorator. Marks a class as a managed component.

    Args:
        name: Optional custom name for the component
        scope: Scope.SINGLETON or Scope.PROTOTYPE (or string "singleton"/"prototype")
    """

    def decorator(cls: Type) -> Type:
        container = get_container()
        container.register(cls, name=name, scope=scope)

        # Store metadata on class for introspection
        cls.__mitsuki_component__ = True
        cls.__mitsuki_name__ = name or cls.__name__
        cls.__mitsuki_scope__ = scope

        return cls

    return decorator


def Service(name: Optional[str] = None, scope: Union[str, Scope] = Scope.SINGLETON):
    """
    Service layer component decorator.
    Semantically equivalent to @Component but indicates service layer.

    Args:
        name: Optional custom name for the service
        scope: Scope.SINGLETON or Scope.PROTOTYPE (or string "singleton"/"prototype")
    """

    def decorator(cls: Type) -> Type:
        container = get_container()
        container.register(cls, name=name, scope=scope)

        cls.__mitsuki_component__ = True
        cls.__mitsuki_service__ = True
        cls.__mitsuki_name__ = name or cls.__name__
        cls.__mitsuki_scope__ = scope

        return cls

    return decorator


def Repository(name: Optional[str] = None, scope: Union[str, Scope] = Scope.SINGLETON):
    """
    Data access layer component decorator.
    Marks a class as a repository for data operations.

    Args:
        name: Optional custom name for the repository
        scope: Scope.SINGLETON or Scope.PROTOTYPE (or string "singleton"/"prototype")
    """

    def decorator(cls: Type) -> Type:
        container = get_container()
        container.register(cls, name=name, scope=scope)

        cls.__mitsuki_component__ = True
        cls.__mitsuki_repository__ = True
        cls.__mitsuki_name__ = name or cls.__name__
        cls.__mitsuki_scope__ = scope

        return cls

    return decorator


def Configuration(cls: Type) -> Type:
    """
    Configuration class decorator.
    Marks a class as a configuration source for providers.
    """
    # Set attributes BEFORE registering so container can detect them
    cls.__mitsuki_configuration__ = True
    cls.__mitsuki_component__ = True

    container = get_container()
    container.register(cls, name=cls.__name__, scope=Scope.SINGLETON)

    return cls


def Provider(
    func: Optional[Callable] = None,
    name: Optional[str] = None,
    scope: Union[Scope, str] = Scope.SINGLETON,
):
    """
    Method decorator for factory methods in @Configuration classes.
    The method's return value will be registered as a component.

    Can be used with or without parentheses:
        @Provider
        def my_provider(self) -> MyType:
            ...

        @Provider(name="customName", scope=Scope.PROTOTYPE)
        def my_provider(self) -> MyType:
            ...

    Args:
        func: The function to decorate (when used without parentheses)
        name: Optional custom name for the provider
        scope: Scope.SINGLETON or Scope.PROTOTYPE (or string "singleton"/"prototype")
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        wrapper.__mitsuki_provider__ = True
        wrapper.__mitsuki_provider_name__ = name or f.__name__
        wrapper.__mitsuki_provider_scope__ = scope

        return wrapper

    # If func is provided, we're being called without parentheses (@Provider)
    if func is not None:
        return decorator(func)

    # Otherwise, we're being called with parentheses (@Provider())
    return decorator
