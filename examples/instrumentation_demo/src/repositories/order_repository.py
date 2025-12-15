from src.domain import Order

from mitsuki.data import CrudRepository


@CrudRepository(entity=Order)
class OrderRepository:
    """
    Repository for Order entities.

    Automatically instrumented when @Instrumented is on @Application.
    All CRUD operations are tracked for timing, errors, and memory usage.
    """

    pass
