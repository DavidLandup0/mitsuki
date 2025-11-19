import tempfile
from typing import Dict, List, Optional, Tuple

from python_multipart.multipart import parse_options_header

from mitsuki.exceptions import (
    FileTooLargeException,
    MultipartParseException,
    RequestTooLargeException,
)
from mitsuki.web.upload import UploadFile


class FormData:
    """Parsed multipart/form-data containing files and fields."""

    def __init__(self):
        self.files: Dict[str, List[UploadFile]] = {}
        self.fields: Dict[str, List[str]] = {}

    def get_file(self, name: str) -> Optional[UploadFile]:
        """Get first uploaded file by field name."""
        files = self.files.get(name, [])
        return files[0] if files else None

    def get_files(self, name: str) -> List[UploadFile]:
        """Get all uploaded files by field name."""
        return self.files.get(name, [])

    def get_field(self, name: str) -> Optional[str]:
        """Get first form field value by name."""
        fields = self.fields.get(name, [])
        return fields[0] if fields else None

    def get_fields(self, name: str) -> List[str]:
        """Get all form field values by name."""
        return self.fields.get(name, [])


async def parse_multipart(
    content_type: str,
    body: bytes,
    max_file_size: Optional[int] = None,
    max_request_size: Optional[int] = None,
) -> FormData:
    """
    Parse multipart/form-data from request body.

    Args:
        content_type: Content-Type header value
        body: Request body bytes
        max_file_size: Maximum size for individual files in bytes
        max_request_size: Maximum size for entire request in bytes

    Returns:
        FormData containing parsed files and fields

    Raises:
        MultipartParseException: If parsing fails
        RequestTooLargeException: If request exceeds max_request_size
    """

    # Check total request size
    if max_request_size and len(body) > max_request_size:
        raise RequestTooLargeException(
            f"Request size {len(body)} exceeds maximum {max_request_size} bytes"
        )

    # Parse content type to get boundary
    content_type_value, options = parse_options_header(content_type)
    if content_type_value != b"multipart/form-data":
        raise MultipartParseException(
            f"Expected multipart/form-data, got {content_type_value}"
        )

    boundary = options.get(b"boundary")
    if not boundary:
        raise MultipartParseException("Missing boundary in Content-Type header")

    form_data = FormData()

    parts = _parse_multipart(body, boundary)

    for part in parts:
        headers = part["headers"]
        content = part["content"]

        # Parse Content-Disposition header
        disposition = headers.get("content-disposition", "")
        name, filename = _parse_content_disposition(disposition)

        if filename:
            # This is a file upload
            content_type_header = headers.get("content-type")

            # Check file size
            if max_file_size and len(content) > max_file_size:
                raise FileTooLargeException(
                    f"File {filename} size {len(content)} exceeds maximum {max_file_size} bytes"
                )

            # Create temp file for uploaded content
            temp_file = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)  # 1MB
            temp_file.write(content)
            temp_file.seek(0)

            upload_file = UploadFile(
                filename=filename,
                file=temp_file,
                content_type=content_type_header,
                size=len(content),
            )

            if name not in form_data.files:
                form_data.files[name] = []
            form_data.files[name].append(upload_file)
        else:
            # This is a regular form field
            value = content.decode("utf-8")
            if name not in form_data.fields:
                form_data.fields[name] = []
            form_data.fields[name].append(value)

    return form_data


def _parse_multipart(body: bytes, boundary: bytes) -> List[Dict]:
    """
    Simple multipart parser without using streaming parser.
    Returns list of parts with headers and content.
    """
    parts = []
    boundary_delimiter = b"--" + boundary
    end_boundary = boundary_delimiter + b"--"

    # Split by boundary
    sections = body.split(boundary_delimiter)

    for section in sections[1:]:  # Skip first empty part
        if section.startswith(b"--") or not section.strip():
            continue

        # Split headers and content
        header_end = section.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        header_bytes = section[:header_end]
        content = section[header_end + 4 :]  # Skip \r\n\r\n

        # Remove trailing \r\n
        if content.endswith(b"\r\n"):
            content = content[:-2]

        # Parse headers
        headers = {}
        for line in header_bytes.split(b"\r\n"):
            if b":" in line:
                key, value = line.split(b":", 1)
                headers[key.decode("utf-8").lower().strip()] = value.decode(
                    "utf-8"
                ).strip()

        parts.append({"headers": headers, "content": content})

    return parts


def _parse_content_disposition(disposition: str) -> Tuple[str, Optional[str]]:
    """
    Parse Content-Disposition header to extract name and filename.

    Returns:
        Tuple of (name, filename). filename is None for regular fields.
    """
    name = None
    filename = None

    # Simple parsing: form-data; name="field"; filename="file.txt"
    parts = disposition.split(";")
    for part in parts:
        part = part.strip()
        if part.startswith("name="):
            name = part[5:].strip('"')
        elif part.startswith("filename="):
            filename = part[9:].strip('"')

    return name or "", filename
