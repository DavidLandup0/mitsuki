"""
Main application entry point.
"""
import os

from mitsuki import Application, Value, get_logger{{CONTROLLER_IMPORT}}


@Application
class App:
    """
    Mitsuki application.

    Configuration is loaded from application.yml and can be overridden
    with environment variables (MITSUKI_SERVER_PORT, etc.)
    """
    port: int = Value("${server.port:8000}")
    host: str = Value("${server.host:127.0.0.1}")


if __name__ == "__main__":
    # Get active profile from environment
    profile = os.getenv("MITSUKI_PROFILE", "development")
    logger = get_logger()
    logger.info(f"Starting Mitsuki application with profile: {profile}")

    App.run()
