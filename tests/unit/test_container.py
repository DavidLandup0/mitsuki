"""
Unit tests for DIContainer - dependency injection and IoC container.
"""

import pytest

from mitsuki.core.container import DIContainer, get_container, set_container
from mitsuki.core.decorators import Component, Repository, Service
from mitsuki.core.enums import Scope, StereotypeType
from mitsuki.exceptions import ComponentNotFoundException


@pytest.fixture(autouse=True)
def reset_container():
    """Reset the global container before each test."""
    set_container(DIContainer())
    yield
    set_container(DIContainer())


class TestBasicRegistration:
    """Tests for basic component registration."""

    def test_register_component(self):
        """Should register a component by class."""

        @Component()
        class MyComponent:
            pass

        container = get_container()
        assert MyComponent in container._components

    def test_register_with_name(self):
        """Should register a component with a custom name."""

        @Component(name="custom_name")
        class MyComponent:
            pass

        container = get_container()
        assert "custom_name" in container._components_by_name

    def test_register_singleton(self):
        """Should register singleton components by default."""

        @Component(scope="singleton")
        class MyComponent:
            pass

        container = get_container()
        metadata = container._components[MyComponent]
        assert metadata.scope == "singleton"

    def test_register_prototype(self):
        """Should register prototype components."""

        @Component(scope="prototype")
        class MyComponent:
            pass

        container = get_container()
        metadata = container._components[MyComponent]
        assert metadata.scope == "prototype"


class TestDependencyInjection:
    """Tests for constructor dependency injection."""

    def test_simple_injection(self):
        """Should inject dependencies into constructor."""

        @Component()
        class ServiceA:
            pass

        @Component()
        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a

        container = get_container()
        b = container.get(ServiceB)
        assert isinstance(b.a, ServiceA)

    def test_multiple_dependencies(self):
        """Should inject multiple dependencies."""

        @Component()
        class ServiceA:
            pass

        @Component()
        class ServiceB:
            pass

        @Component()
        class ServiceC:
            def __init__(self, a: ServiceA, b: ServiceB):
                self.a = a
                self.b = b

        container = get_container()
        c = container.get(ServiceC)
        assert isinstance(c.a, ServiceA)
        assert isinstance(c.b, ServiceB)

    def test_nested_dependencies(self):
        """Should resolve nested dependency chains."""

        @Component()
        class ServiceA:
            pass

        @Component()
        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a

        @Component()
        class ServiceC:
            def __init__(self, b: ServiceB):
                self.b = b

        container = get_container()
        c = container.get(ServiceC)
        assert isinstance(c.b, ServiceB)
        assert isinstance(c.b.a, ServiceA)


class TestSingletonScope:
    """Tests for singleton scope behavior."""

    def test_singleton_returns_same_instance(self):
        """Singleton components should return the same instance."""

        @Component()
        class SingletonService:
            pass

        container = get_container()
        instance1 = container.get(SingletonService)
        instance2 = container.get(SingletonService)
        assert instance1 is instance2

    def test_singleton_with_dependencies(self):
        """Singleton dependencies should be reused."""

        @Component()
        class ServiceA:
            pass

        @Component()
        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a

        @Component()
        class ServiceC:
            def __init__(self, a: ServiceA):
                self.a = a

        container = get_container()
        b = container.get(ServiceB)
        c = container.get(ServiceC)
        assert b.a is c.a  # Same ServiceA instance


class TestPrototypeScope:
    """Tests for prototype scope behavior."""

    def test_prototype_returns_new_instance(self):
        """Prototype components should return new instances."""

        @Component(scope="prototype")
        class PrototypeService:
            pass

        container = get_container()
        instance1 = container.get(PrototypeService)
        instance2 = container.get(PrototypeService)
        assert instance1 is not instance2

    def test_prototype_with_singleton_dependency(self):
        """Prototype can depend on singleton."""

        @Component()
        class SingletonService:
            pass

        @Component(scope="prototype")
        class PrototypeService:
            def __init__(self, singleton: SingletonService):
                self.singleton = singleton

        container = get_container()
        proto1 = container.get(PrototypeService)
        proto2 = container.get(PrototypeService)
        assert proto1 is not proto2
        assert proto1.singleton is proto2.singleton  # Same singleton

    def test_prototype_with_prototype_dependency(self):
        """Prototype can depend on prototype."""

        @Component(scope="prototype")
        class FirstPrototypeService:
            pass

        @Component(scope="prototype")
        class SecondPrototypeService:
            def __init__(self, prototype: FirstPrototypeService):
                self.prototype = prototype

        container = get_container()
        proto1 = container.get(SecondPrototypeService)
        proto2 = container.get(SecondPrototypeService)
        assert proto1 is not proto2
        assert proto1.prototype is not proto2.prototype  # Different instances


class TestGetByName:
    """Tests for getting components by name."""

    def test_get_by_name(self):
        """Should retrieve component by name."""

        @Component(name="my_service")
        class MyService:
            pass

        container = get_container()
        service = container.get_by_name("my_service")
        assert isinstance(service, MyService)

    def test_get_by_name_not_found(self):
        """Should raise error when name not found."""
        container = get_container()

        with pytest.raises(ComponentNotFoundException, match="not registered"):
            container.get_by_name("nonexistent")

    def test_get_by_name_with_custom_name(self):
        """Should use custom name when provided."""

        @Component(name="custom")
        class MyService:
            pass

        container = get_container()
        service = container.get_by_name("custom")
        assert isinstance(service, MyService)


class TestStereotypeDecorators:
    """Tests for @Service and @Repository decorators."""

    def test_service_decorator(self):
        """@Service should register as component."""

        @Service()
        class MyService:
            pass

        container = get_container()
        service = container.get(MyService)
        assert isinstance(service, MyService)
        assert MyService._stereotype_subtype == StereotypeType.SERVICE

    def test_repository_decorator(self):
        """@Repository should register as component."""

        @Repository()
        class MyRepository:
            pass

        container = get_container()
        repo = container.get(MyRepository)
        assert isinstance(repo, MyRepository)
        assert MyRepository._stereotype_subtype == StereotypeType.REPOSITORY

    def test_service_with_dependencies(self):
        """@Service can have dependencies."""

        @Repository()
        class UserRepository:
            pass

        @Service()
        class UserService:
            def __init__(self, repo: UserRepository):
                self.repo = repo

        container = get_container()
        service = container.get(UserService)
        assert isinstance(service.repo, UserRepository)


class TestNonClassTypes:
    """Tests for non-class type injection (primitives, etc)."""

    def test_primitive_not_injectable(self):
        """Primitive types should not be auto-injected."""

        @Component()
        class ServiceWithPrimitive:
            def __init__(self, value: int):
                self.value = value

        container = get_container()
        # Should fail because int is not a registered component
        with pytest.raises(Exception):
            container.get(ServiceWithPrimitive)


class TestComponentMetadata:
    """Tests for component metadata storage."""

    def test_metadata_stored(self):
        """Should store component metadata."""

        @Component(name="test", scope="singleton")
        class MyComponent:
            pass

        container = get_container()
        metadata = container._components[MyComponent]
        assert metadata.name == "test"  # Custom name provided
        assert metadata.scope == "singleton"

    def test_mitsuki_attributes_set(self):
        """@Component should set __mitsuki_* attributes."""

        @Component(name="custom", scope="singleton")
        class MyComponent:
            pass

        assert MyComponent._stereotype == StereotypeType.COMPONENT
        assert MyComponent.__mitsuki_name__ == "custom"
        assert MyComponent.__mitsuki_scope__ == "singleton"


class TestContainerReset:
    """Tests for container reset and isolation."""

    def test_set_container_replaces_global(self):
        """set_container should replace the global container."""
        container1 = get_container()

        @Component()
        class Service1:
            pass

        assert Service1 in container1._components

        # Reset container
        set_container(DIContainer())
        container2 = get_container()

        assert Service1 not in container2._components
        assert container1 is not container2


class TestScopeEnum:
    """Tests for using Scope enum instead of strings."""

    def test_component_with_scope_enum_singleton(self):
        """@Component should accept Scope.SINGLETON enum."""

        @Component(scope=Scope.SINGLETON)
        class SingletonService:
            pass

        container = get_container()
        instance1 = container.get(SingletonService)
        instance2 = container.get(SingletonService)
        assert instance1 is instance2

    def test_component_with_scope_enum_prototype(self):
        """@Component should accept Scope.PROTOTYPE enum."""

        @Component(scope=Scope.PROTOTYPE)
        class PrototypeService:
            pass

        container = get_container()
        instance1 = container.get(PrototypeService)
        instance2 = container.get(PrototypeService)
        assert instance1 is not instance2

    def test_service_with_scope_enum(self):
        """@Service should accept Scope enum."""

        @Service(scope=Scope.PROTOTYPE)
        class MyService:
            pass

        container = get_container()
        instance1 = container.get(MyService)
        instance2 = container.get(MyService)
        assert instance1 is not instance2

    def test_repository_with_scope_enum(self):
        """@Repository should accept Scope enum."""

        @Repository(scope=Scope.PROTOTYPE)
        class MyRepo:
            pass

        container = get_container()
        instance1 = container.get(MyRepo)
        instance2 = container.get(MyRepo)
        assert instance1 is not instance2

    def test_scope_enum_default_is_singleton(self):
        """Default scope should be SINGLETON."""

        @Component()
        class DefaultScopeService:
            pass

        container = get_container()
        metadata = container._components[DefaultScopeService]
        assert metadata.scope == Scope.SINGLETON

    def test_backwards_compatibility_with_string_scope(self):
        """Should still accept string 'singleton' and 'prototype' for backwards compatibility."""

        @Component(scope="prototype")
        class StringScopeService:
            pass

        container = get_container()
        instance1 = container.get(StringScopeService)
        instance2 = container.get(StringScopeService)
        assert instance1 is not instance2
