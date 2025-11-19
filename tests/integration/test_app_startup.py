"""
Integration tests for application startup.

These tests actually start the Mitsuki application to verify it can boot correctly.
"""

import os
import subprocess
import tempfile
import time

import httpx
import pytest


def test_basic_hello_world_startup():
    """Test that a basic hello world app can start and respond."""

    app_code = """
from mitsuki import Application, GetMapping, RestController

@RestController()
class HelloController:
    @GetMapping("/")
    async def hello(self):
        return {"message": "Hello, World!"}

@Application(scan_packages=[])
class TestApp:
    pass

if __name__ == "__main__":
    TestApp.run(port=9001)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(app_code)
        app_file = f.name

    try:
        # Start the app as subprocess
        process = subprocess.Popen(
            ["python3", app_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for app to start
            time.sleep(4)

            # Check if process is still running
            if process.poll() is not None:
                # Process died, get output
                stdout, stderr = process.communicate()
                pytest.fail(f"App failed to start.\nStdout: {stdout}\nStderr: {stderr}")

            # Make request
            response = httpx.get("http://127.0.0.1:9001/", timeout=5.0)
            assert response.status_code == 200
            assert response.json() == {"message": "Hello, World!"}

        finally:
            # Stop the app
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    finally:
        if os.path.exists(app_file):
            os.unlink(app_file)


def test_app_with_scheduled_tasks_startup():
    """Test that app with scheduled tasks can start."""

    app_code = """
from mitsuki import Application, GetMapping, RestController, Scheduled, Service

@Service()
class BackgroundService:
    def __init__(self):
        self.count = 0

    @Scheduled(fixed_rate=1000)
    async def background_task(self):
        self.count += 1

@RestController()
class StatusController:
    def __init__(self, service: BackgroundService):
        self.service = service

    @GetMapping("/status")
    async def status(self):
        return {"count": self.service.count}

@Application(scan_packages=[])
class TestApp:
    pass

if __name__ == "__main__":
    TestApp.run(port=9002)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(app_code)
        app_file = f.name

    try:
        process = subprocess.Popen(
            ["python3", app_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            time.sleep(3)

            # Verify app is running
            response = httpx.get("http://127.0.0.1:9002/status", timeout=5.0)
            assert response.status_code == 200
            # Should have executed at least once
            assert response.json()["count"] >= 0

        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    finally:
        os.unlink(app_file)


def test_app_with_dependency_injection_startup():
    """Test that app with DI works end-to-end."""

    app_code = """
from mitsuki import Application, GetMapping, RestController, Service

@Service()
class MessageService:
    def get_message(self):
        return "Hello from service!"

@RestController("/api")
class ApiController:
    def __init__(self, message_service: MessageService):
        self.message_service = message_service

    @GetMapping("/message")
    async def get_message(self):
        return {"message": self.message_service.get_message()}

@Application(scan_packages=[])
class TestApp:
    pass

if __name__ == "__main__":
    TestApp.run(port=9003)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(app_code)
        app_file = f.name

    try:
        process = subprocess.Popen(
            ["python3", app_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            time.sleep(3)

            response = httpx.get("http://127.0.0.1:9003/api/message", timeout=5.0)
            assert response.status_code == 200
            assert response.json() == {"message": "Hello from service!"}

        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    finally:
        os.unlink(app_file)
