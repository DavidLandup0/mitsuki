import os
import shutil
from typing import BinaryIO, Optional


class UploadFile:
    """
    Represents an uploaded file from multipart/form-data request.

    Attributes:
        filename: Original filename from the upload
        content_type: MIME type of the file
        size: Size of the file in bytes
        file: File-like object for reading content
    """

    def __init__(
        self,
        filename: str,
        file: BinaryIO,
        content_type: Optional[str] = None,
        size: Optional[int] = None,
    ):
        self.filename = filename
        self.file = file
        self.content_type = content_type
        self._size = size

    @property
    def size(self) -> int:
        """Get file size in bytes."""
        if self._size is not None:
            return self._size

        # Calculate size by seeking to end
        current_pos = self.file.tell()
        self.file.seek(0, os.SEEK_END)
        self._size = self.file.tell()
        self.file.seek(current_pos)
        return self._size

    async def read(self, size: int = -1) -> bytes:
        """
        Read file content.

        Args:
            size: Number of bytes to read. -1 reads entire file.

        Returns:
            Bytes read from file
        """
        return self.file.read(size)

    async def seek(self, offset: int) -> int:
        """
        Seek to position in file.

        Args:
            offset: Position to seek to

        Returns:
            New position in file
        """
        return self.file.seek(offset)

    async def save(self, destination: str) -> None:
        """
        Save uploaded file to destination path.

        Args:
            destination: Path to save file to

        Example:
            await file.save("uploads/image.jpg")
        """
        # Create directory if it doesn't exist
        directory = os.path.dirname(destination)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        # Reset file pointer to beginning
        self.file.seek(0)

        # Copy file
        with open(destination, "wb") as dest_file:
            shutil.copyfileobj(self.file, dest_file)

        # Reset file pointer again
        self.file.seek(0)

    def close(self) -> None:
        """Close the underlying file."""
        self.file.close()

    def __repr__(self) -> str:
        return f"UploadFile(filename={self.filename!r}, content_type={self.content_type!r}, size={self.size})"
