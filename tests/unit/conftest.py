import pytest

from mitsuki.core.container import DIContainer, get_container, set_container


@pytest.fixture
def isolated_container():
    """Swap in a fresh DI container for the duration of a test."""
    previous = get_container()
    set_container(DIContainer())
    try:
        yield get_container()
    finally:
        set_container(previous)
