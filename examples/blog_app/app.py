from mitsuki import Application


@Application
class BlogApp:
    """Blog application configuration."""

    # You can define your configurations here if you'd prefer it
    # over application.yml

    # port: int = 8000
    # database_url: str = "sqlite+aiosqlite:///blog.db"
    # database_adapter: str = "sqlalchemy"
    pass


if __name__ == "__main__":
    BlogApp.run()
