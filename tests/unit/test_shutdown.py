from unittest.mock import AsyncMock, patch

import pytest

from mitsuki.core.server import MitsukiASGIApp


class MockContext:
    """Mock application context for testing."""

    def __init__(self):
        self.controllers = []

    def _scan_scheduled_tasks(self):
        """Mock scheduled task scanning."""
        pass


class TestShutdownCleanup:
    """Tests for ASGI lifespan shutdown cleanup."""

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_disconnects_database(self):
        """Should call database disconnect on shutdown."""
        app = MitsukiASGIApp(MockContext())

        mock_adapter = AsyncMock()
        mock_adapter.disconnect = AsyncMock()

        with patch(
            "mitsuki.core.server.get_database_adapter", return_value=mock_adapter
        ):
            # Enter and exit the lifespan context to trigger startup/shutdown
            async with app._lifespan(None):
                pass

        mock_adapter.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_handles_no_database(self):
        """Should handle shutdown gracefully when database not initialized."""
        app = MitsukiASGIApp(MockContext())

        with patch(
            "mitsuki.core.server.get_database_adapter",
            side_effect=RuntimeError("Database not initialized"),
        ):
            # Enter and exit the lifespan context - should not raise
            async with app._lifespan(None):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_startup(self):
        """Should respond to startup event."""
        app = MitsukiASGIApp(MockContext())

        # Enter the lifespan context to trigger startup
        async with app._lifespan(None):
            # If we get here, startup succeeded
            pass
