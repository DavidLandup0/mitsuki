from mitsuki import Application


@Application
class BlogApp:
    """Blog application configuration."""

    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///blog.db"
    database_adapter: str = "sqlalchemy"


if __name__ == "__main__":
    BlogApp.run()
