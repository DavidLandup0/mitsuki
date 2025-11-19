"""
Simple tests for file upload functionality.
"""

import os
import shutil
import tempfile
from typing import List, Optional

from starlette.testclient import TestClient

from mitsuki import FormFile, FormParam, PostMapping, RestController
from mitsuki.core.container import DIContainer, set_container
from mitsuki.core.server import MitsukiASGIApp
from mitsuki.web.upload import UploadFile


class MockContext:
    """Mock application context for testing."""

    def __init__(self):
        self.controllers = []


class TestSingleFileUpload:
    """Tests for single file upload."""

    def setup_method(self):
        set_container(DIContainer())

    def teardown_method(self):
        set_container(DIContainer())

    def test_single_file_upload(self):
        """Test uploading a single file."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(self, file: UploadFile = FormFile()) -> dict:
                content = await file.read()
                return {
                    "filename": file.filename,
                    "size": file.size,
                    "content_type": file.content_type,
                    "content": content.decode("utf-8"),
                }

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        # Create test file
        files = {"file": ("test.txt", b"Hello, World!", "text/plain")}
        response = client.post("/api/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.txt"
        assert data["content"] == "Hello, World!"
        assert data["content_type"] == "text/plain"
        assert data["size"] == 13

    def test_optional_file_not_provided(self):
        """Test optional file when not provided."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(
                self,
                file: Optional[UploadFile] = FormFile(required=False),
                title: str = FormParam(),
            ) -> dict:
                return {
                    "has_file": file is not None,
                    "title": title,
                }

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        # Send form data as multipart (files with empty dict still sends multipart)
        # Must send as multipart because FormParam expects multipart/form-data
        data = {"title": "No File Upload"}
        # Send empty file field to make it multipart
        files = {"file": ("", b"", "")}  # Empty filename, no content = no file
        response = client.post("/api/upload", data=data, files=files)

        assert response.status_code == 200
        result = response.json()
        assert result["has_file"] is False  # Empty file is treated as no file
        assert result["title"] == "No File Upload"


class TestFileWithFormData:
    """Tests for file upload combined with form data."""

    def setup_method(self):
        set_container(DIContainer())

    def teardown_method(self):
        set_container(DIContainer())

    def test_file_with_form_fields(self):
        """Test uploading file with additional form fields."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(
                self,
                file: UploadFile = FormFile(),
                title: str = FormParam(),
                description: str = FormParam(default=""),
            ) -> dict:
                return {
                    "filename": file.filename,
                    "title": title,
                    "description": description,
                }

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        # Upload file with form data
        files = {"file": ("doc.pdf", b"PDF content", "application/pdf")}
        data = {"title": "My Document", "description": "Important file"}
        response = client.post("/api/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["filename"] == "doc.pdf"
        assert result["title"] == "My Document"
        assert result["description"] == "Important file"


class TestMultipleFileUpload:
    """Tests for uploading multiple files."""

    def setup_method(self):
        set_container(DIContainer())

    def teardown_method(self):
        set_container(DIContainer())

    def test_multiple_files_upload(self):
        """Test uploading multiple files at once."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(self, files: List[UploadFile] = FormFile()) -> dict:
                filenames = []
                total_size = 0
                for file in files:
                    filenames.append(file.filename)
                    total_size += file.size
                return {
                    "count": len(files),
                    "filenames": filenames,
                    "total_size": total_size,
                }

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        # Upload multiple files with same field name
        files = [
            ("files", ("file1.txt", b"Content 1", "text/plain")),
            ("files", ("file2.txt", b"Content 2", "text/plain")),
            ("files", ("file3.pdf", b"PDF content", "application/pdf")),
        ]
        response = client.post("/api/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert "file1.txt" in data["filenames"]
        assert "file2.txt" in data["filenames"]
        assert "file3.pdf" in data["filenames"]
        assert data["total_size"] == 9 + 9 + 11


class TestFileSave:
    """Tests for saving uploaded files to disk."""

    def setup_method(self):
        set_container(DIContainer())

    def teardown_method(self):
        set_container(DIContainer())

    def test_save_file_to_disk(self):
        """Test saving uploaded file to disk."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(self, file: UploadFile = FormFile()) -> dict:
                # Create temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
                    dest_path = tmp.name

                # Save the uploaded file
                await file.save(dest_path)

                # Verify file was saved
                with open(dest_path, "rb") as f:
                    saved_content = f.read()

                # Cleanup
                os.unlink(dest_path)

                return {
                    "filename": file.filename,
                    "saved": True,
                    "content_match": saved_content == b"Test file content",
                }

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        files = {"file": ("upload.txt", b"Test file content", "text/plain")}
        response = client.post("/api/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["saved"] is True
        assert data["content_match"] is True

    def test_save_file_creates_directory(self):
        """Test that save() creates parent directories if needed."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(self, file: UploadFile = FormFile()) -> dict:
                # Create a path with non-existent directories
                temp_dir = tempfile.mkdtemp()
                dest_path = os.path.join(temp_dir, "subdir1", "subdir2", "file.txt")

                # Save should create the directories
                await file.save(dest_path)

                # Verify file exists
                exists = os.path.exists(dest_path)

                # Verify content
                with open(dest_path, "rb") as f:
                    content = f.read()

                # Cleanup
                shutil.rmtree(temp_dir)

                return {"exists": exists, "content_correct": content == b"File content"}

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        files = {"file": ("test.txt", b"File content", "text/plain")}
        response = client.post("/api/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["content_correct"] is True


class TestFileSizeValidation:
    """Tests for file size validation."""

    def setup_method(self):
        set_container(DIContainer())

    def teardown_method(self):
        set_container(DIContainer())

    def test_file_within_size_limit(self):
        """Test file upload within size limit."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(
                self,
                file: UploadFile = FormFile(max_size=1024),  # 1KB limit
            ) -> dict:
                return {"filename": file.filename, "size": file.size}

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        # Upload small file
        files = {"file": ("small.txt", b"x" * 512, "text/plain")}
        response = client.post("/api/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["size"] == 512

    def test_file_exceeds_size_limit(self):
        """Test that file exceeding size limit returns 400."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(
                self,
                file: UploadFile = FormFile(max_size=100),  # 100 bytes limit
            ) -> dict:
                return {"filename": file.filename}

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        # Upload file that's too large
        files = {"file": ("large.txt", b"x" * 200, "text/plain")}
        response = client.post("/api/upload", files=files)

        assert response.status_code == 400
        assert "error" in response.json()
        assert "exceeds maximum size" in response.json()["error"].lower()


class TestFileTypeValidation:
    """Tests for file type validation."""

    def setup_method(self):
        set_container(DIContainer())

    def teardown_method(self):
        set_container(DIContainer())

    def test_allowed_file_types(self):
        """Test file type validation with allowed types."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(
                self,
                image: UploadFile = FormFile(
                    allowed_types=["image/jpeg", "image/png", "image/gif"]
                ),
            ) -> dict:
                return {"filename": image.filename, "type": image.content_type}

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        # Upload allowed file type
        files = {"image": ("photo.jpg", b"fake image data", "image/jpeg")}
        response = client.post("/api/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "photo.jpg"
        assert data["type"] == "image/jpeg"

    def test_invalid_file_type(self):
        """Test that invalid file type returns 400."""

        @RestController("/api")
        class UploadController:
            @PostMapping("/upload")
            async def upload(
                self,
                image: UploadFile = FormFile(allowed_types=["image/jpeg", "image/png"]),
            ) -> dict:
                return {"filename": image.filename}

        context = MockContext()
        context.controllers = [(UploadController, "/api")]
        app = MitsukiASGIApp(context)
        client = TestClient(app)

        # Upload disallowed file type
        files = {"image": ("document.pdf", b"PDF content", "application/pdf")}
        response = client.post("/api/upload", files=files)

        assert response.status_code == 400
        assert "error" in response.json()
        assert "not allowed" in response.json()["error"].lower()
