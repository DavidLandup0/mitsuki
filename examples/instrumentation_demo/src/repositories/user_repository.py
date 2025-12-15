from src.domain import User

from mitsuki.data import CrudRepository


@CrudRepository(entity=User)
class UserRepository:
    """
    Repository for User entities.

    Automatically instrumented when @Instrumented is on @Application.
    All CRUD operations are tracked for timing, errors, and memory usage.
    """

    pass
