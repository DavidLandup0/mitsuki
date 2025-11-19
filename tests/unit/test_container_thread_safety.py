"""
Tests for thread-safety in DIContainer singleton creation.
"""

import threading
import time

from mitsuki.core.container import DIContainer


class ExpensiveSingleton:
    """Singleton with slow initialization to trigger race conditions."""

    instance_count = 0

    def __init__(self):
        # Simulate expensive initialization
        time.sleep(0.01)
        ExpensiveSingleton.instance_count += 1
        self.id = ExpensiveSingleton.instance_count


class SingletonWithDependency:
    """Singleton that depends on another singleton."""

    def __init__(self, dep: ExpensiveSingleton):
        self.dep = dep


def test_singleton_created_once_under_concurrent_access():
    """Test that singleton is only created once even with concurrent get() calls."""
    ExpensiveSingleton.instance_count = 0

    container = DIContainer()
    container.register(ExpensiveSingleton, scope="singleton")

    instances = []
    errors = []

    def get_instance():
        try:
            instance = container.get(ExpensiveSingleton)
            instances.append(instance)
        except Exception as e:
            errors.append(e)

    # Create 10 threads that try to get the singleton simultaneously
    threads = []
    for _ in range(10):
        t = threading.Thread(target=get_instance)
        threads.append(t)

    # Start all threads at once
    for t in threads:
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Verify no errors
    assert len(errors) == 0, f"Errors occurred: {errors}"

    # Verify we got 10 instances back
    assert len(instances) == 10

    # Verify only ONE instance was created (all references are the same)
    assert ExpensiveSingleton.instance_count == 1
    assert all(inst is instances[0] for inst in instances)
    assert all(inst.id == 1 for inst in instances)


def test_singleton_with_dependencies_created_once():
    """Test that singletons with dependencies are only created once."""
    ExpensiveSingleton.instance_count = 0

    container = DIContainer()
    container.register(ExpensiveSingleton, scope="singleton")
    container.register(SingletonWithDependency, scope="singleton")

    instances = []

    def get_instance():
        instance = container.get(SingletonWithDependency)
        instances.append(instance)

    threads = []
    for _ in range(10):
        t = threading.Thread(target=get_instance)
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Verify only ONE instance of each singleton was created
    assert ExpensiveSingleton.instance_count == 1
    assert len(instances) == 10
    assert all(inst is instances[0] for inst in instances)
    assert all(inst.dep is instances[0].dep for inst in instances)


def test_prototype_creates_multiple_instances():
    """Test that prototype scope creates new instances."""
    ExpensiveSingleton.instance_count = 0

    container = DIContainer()
    container.register(ExpensiveSingleton, scope="prototype")

    instances = []

    def get_instance():
        instance = container.get(ExpensiveSingleton)
        instances.append(instance)

    threads = []
    for _ in range(5):
        t = threading.Thread(target=get_instance)
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Verify 5 different instances were created
    assert ExpensiveSingleton.instance_count == 5
    assert len(instances) == 5

    # Verify they're all different instances
    ids = [inst.id for inst in instances]
    assert len(set(ids)) == 5  # All unique IDs
