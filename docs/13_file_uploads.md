# File Uploads

## Table of Contents

- [Overview](#overview)
- [Basic File Upload](#basic-file-upload)
- [File Validation](#file-validation)
- [Multiple File Uploads](#multiple-file-uploads)
- [File Upload with Form Data](#file-upload-with-form-data)
- [Saving Files to Disk](#saving-files-to-disk)
- [Configuration](#configuration)
- [Complete Examples](#complete-examples)
- [Best Practices](#best-practices)


## Overview

Mitsuki provides built-in support for handling file uploads through multipart/form-data requests. The framework offers:

- **Type-safe file handling** - `UploadFile` class for uploaded files
- **Automatic validation** - File type and size validation
- **Form parameter mixing** - Combine files with regular form fields
- **Multiple file support** - Upload multiple files in a single request
- **Streaming support** - Efficient handling of large files
- **Easy file saving** - Save files to disk with directory creation

## Basic File Upload

### Single File Upload

```python
from mitsuki import RestController, PostMapping, FormFile, UploadFile

@RestController("/api/uploads")
class UploadController:
    @PostMapping("/")
    async def upload_file(self, file: UploadFile = FormFile()) -> dict:
        """Upload a single file."""
        content = await file.read()

        return {
            "filename": file.filename,
            "size": file.size,
            "content_type": file.content_type,
        }
```

### UploadFile Properties

The `UploadFile` object provides:

- `filename: str` - Original filename from client
- `file: BinaryIO` - File-like object for reading
- `content_type: Optional[str]` - MIME type (e.g., "image/jpeg")
- `size: int` - File size in bytes

### Reading File Content

```python
@PostMapping("/process")
async def process_file(self, file: UploadFile = FormFile()) -> dict:
    # Read entire file
    content = await file.read()

    # Read in chunks
    chunk = await file.read(1024)  # Read 1KB

    # File is seekable
    file.file.seek(0)  # Reset to beginning
```


## File Validation

### File Type Validation

Restrict uploads to specific MIME types:

```python
@PostMapping("/upload-image")
async def upload_image(
    self,
    image: UploadFile = FormFile(
        allowed_types=["image/jpeg", "image/png", "image/gif"]
    ),
) -> dict:
    """Only accept JPEG, PNG, and GIF images."""
    return {
        "filename": image.filename,
        "type": image.content_type,
        "size": image.size,
    }
```

Invalid file types return HTTP 400:

```json
{
  "error": "File type application/pdf not allowed"
}
```

### File Size Validation

Set maximum file size per upload:

```python
@PostMapping("/upload-avatar")
async def upload_avatar(
    self,
    avatar: UploadFile = FormFile(
        max_size=2 * 1024 * 1024,  # 2MB limit
        allowed_types=["image/jpeg", "image/png"]
    ),
) -> dict:
    """Upload avatar with 2MB size limit."""
    await avatar.save(f"avatars/{avatar.filename}")
    return {"message": "Avatar uploaded"}
```

Files exceeding the limit return HTTP 400:

```json
{
  "error": "File avatar.jpg size 3145728 exceeds maximum 2097152 bytes"
}
```

### Combined Validation

```python
@PostMapping("/upload-document")
async def upload_document(
    self,
    document: UploadFile = FormFile(
        allowed_types=["application/pdf", "application/msword"],
        max_size=10 * 1024 * 1024,  # 10MB
    ),
) -> dict:
    """Upload PDF or Word document up to 10MB."""
    return {"filename": document.filename}
```

### Optional Files

Make file uploads optional:

```python
@PostMapping("/create-post")
async def create_post(
    self,
    title: str = FormParam(),
    image: Optional[UploadFile] = FormFile(required=False),
) -> dict:
    """Create post with optional image."""
    result = {"title": title}

    if image:
        await image.save(f"posts/{image.filename}")
        result["image"] = image.filename

    return result
```


## Multiple File Uploads

### Upload Multiple Files

```python
from typing import List

@PostMapping("/upload-gallery")
async def upload_gallery(
    self,
    images: List[UploadFile] = FormFile(
        allowed_types=["image/jpeg", "image/png"]
    ),
) -> dict:
    """Upload multiple images at once."""
    uploaded = []

    for image in images:
        await image.save(f"gallery/{image.filename}")
        uploaded.append({
            "filename": image.filename,
            "size": image.size,
        })

    return {
        "count": len(images),
        "files": uploaded,
    }
```

### Client Request Example

Upload multiple files using the same field name:

```bash
curl -X POST http://localhost:8000/api/upload-gallery \
  -F "images=@photo1.jpg" \
  -F "images=@photo2.jpg" \
  -F "images=@photo3.png"
```


## File Upload with Form Data

### Mixing Files and Form Fields

Combine file uploads with regular form parameters:

```python
@PostMapping("/upload-with-metadata")
async def upload_with_metadata(
    self,
    file: UploadFile = FormFile(),
    title: str = FormParam(),
    description: str = FormParam(default=""),
    tags: str = FormParam(default=""),
) -> dict:
    """Upload file with additional metadata."""
    await file.save(f"uploads/{file.filename}")

    return {
        "filename": file.filename,
        "title": title,
        "description": description,
        "tags": tags.split(",") if tags else [],
    }
```

### Client Request

```bash
curl -X POST http://localhost:8000/api/upload-with-metadata \
  -F "file=@document.pdf" \
  -F "title=My Document" \
  -F "description=Important file" \
  -F "tags=work,2024"
```

### Multiple Files with Metadata

```python
@PostMapping("/upload-post")
async def upload_post(
    self,
    title: str = FormParam(),
    content: str = FormParam(),
    images: List[UploadFile] = FormFile(required=False),
    attachments: List[UploadFile] = FormFile(required=False),
) -> dict:
    """Upload post with multiple image and attachment fields."""
    result = {
        "title": title,
        "content": content,
        "images": [],
        "attachments": [],
    }

    if images:
        for img in images:
            await img.save(f"posts/images/{img.filename}")
            result["images"].append(img.filename)

    if attachments:
        for att in attachments:
            await att.save(f"posts/attachments/{att.filename}")
            result["attachments"].append(att.filename)

    return result
```


## Saving Files to Disk

### Basic File Save

```python
@PostMapping("/upload")
async def upload(self, file: UploadFile = FormFile()) -> dict:
    """Save uploaded file to disk."""
    # Save to specific path
    await file.save("/var/uploads/myfile.pdf")

    return {"message": "File saved"}
```

## Configuration

### Global Upload Limits

Configure upload limits in `application.yml`:

```yaml
server:
  max_body_size: 10485760  # 10MB total request size
  multipart:
    max_file_size: 10485760  # 10MB per file (default)
    max_request_size: 52428800  # 50MB total request (default)
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `server.max_body_size` | 10MB | Maximum request body size |
| `server.multipart.max_file_size` | 10MB | Maximum size per file |
| `server.multipart.max_request_size` | 50MB | Maximum total request size |

### Environment Variables

Override via environment variables:

```bash
# Set max file size to 20MB
MITSUKI_SERVER_MULTIPART_MAX_FILE_SIZE=20971520

# Set max request size to 100MB
MITSUKI_SERVER_MULTIPART_MAX_REQUEST_SIZE=104857600
```

## Best Practices

### Security

1. **Validate file types** - Always use `allowed_types` to restrict uploads
2. **Set size limits** - Use `max_size` to prevent large file attacks
3. **Sanitize filenames** - Don't trust client-provided filenames
4. **Scan for malware** - Consider virus scanning for user uploads

### Performance

1. **Stream large files** - Use `file.read(chunk_size)` for large files
2. **Set appropriate limits** - Configure `max_file_size` based on your needs
3. **Use async I/O** - Use `await file.save()` for non-blocking I/O
4. **Consider cloud storage** - For production, consider using S3, GCS, or Azure Blob Storage

### Error Handling

```python
from mitsuki.exceptions import FileTooLargeException, InvalidFileTypeException

@PostMapping("/upload")
async def upload(self, file: UploadFile = FormFile()) -> dict:
    try:
        await file.save(f"uploads/{file.filename}")
        return {"message": "Success"}
    except FileTooLargeException as e:
        return ResponseEntity.bad_request({"error": str(e)})
    except InvalidFileTypeException as e:
        return ResponseEntity.bad_request({"error": str(e)})
    except Exception as e:
        return ResponseEntity.server_error({"error": "Upload failed"})
```

### Validation Examples

```python
# Images only
image: UploadFile = FormFile(
    allowed_types=["image/jpeg", "image/png", "image/gif"]
)

# Documents only
doc: UploadFile = FormFile(
    allowed_types=[
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
)

# Small avatar
avatar: UploadFile = FormFile(
    allowed_types=["image/jpeg", "image/png"],
    max_size=2 * 1024 * 1024,  # 2MB
)

# Large video
video: UploadFile = FormFile(
    allowed_types=["video/mp4", "video/quicktime"],
    max_size=100 * 1024 * 1024,  # 100MB
)
```


## Next Steps

- [Controllers](./04_controllers.md) - REST API development
- [Request/Response Validation](./10_request_response_validation.md) - Data validation
- [Configuration](./06_configuration.md) - Configure upload limits
