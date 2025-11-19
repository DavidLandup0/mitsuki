from functools import wraps
from typing import Callable


def Query(query_string: str, native: bool = False, modifying: bool = False):
    """
    Decorator for custom SQL queries in repository methods.

    Supports both SQLAlchemy ORM syntax and native SQL.

    Args:
        query_string: SQL query string with :param_name placeholders
        native: If True, execute as native SQL. If False, use SQLAlchemy ORM (default)
        modifying: If True, query is UPDATE/DELETE (set automatically by @Modifying)

    Example:
        @Query("SELECT u FROM User u WHERE u.email = :email")
        async def find_by_custom_email(self, email: str) -> Optional[User]: ...

        @Query("SELECT * FROM users WHERE age > :min_age", native=True)
        async def find_adults_native(self, min_age: int) -> List[User]: ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Store query metadata on the function
        wrapper.__mitsuki_query__ = True
        wrapper.__mitsuki_query_string__ = query_string
        wrapper.__mitsuki_query_native__ = native
        wrapper.__mitsuki_query_modifying__ = modifying

        return wrapper

    return decorator


def Modifying(func: Callable) -> Callable:
    """
    Marks a query as modifying (UPDATE/DELETE).

    Modifying queries:
    - Automatically commit after execution
    - Return the number of affected rows
    - Should be used with @Query decorator

    Example:
        @Modifying
        @Query("UPDATE User u SET u.active = :status WHERE u.age > :age")
        async def deactivate_old_users(self, age: int, status: bool) -> int: ...

    Returns:
        Decorated function with modifying flag set
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    # Copy all query metadata from @Query decorator and set modifying=True
    wrapper.__mitsuki_query__ = func.__mitsuki_query__
    wrapper.__mitsuki_query_string__ = func.__mitsuki_query_string__
    wrapper.__mitsuki_query_native__ = func.__mitsuki_query_native__
    wrapper.__mitsuki_query_modifying__ = True

    return wrapper
