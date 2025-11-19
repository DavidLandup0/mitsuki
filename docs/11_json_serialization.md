# JSON Serialization

Mitsuki provides robust JSON serialization with support for Python types not natively supported by the standard `json` library.

## Table of Contents

- [Overview](#overview)
- [Built-in Type Support](#built-in-type-support)
- [Basic Usage](#basic-usage)
- [Custom Serializers](#custom-serializers)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)


## Overview

Mitsuki's JSON serialization module (`mitsuki.web.serialization`) automatically handles common Python types that the standard library cannot serialize:

- `datetime`, `date`, `time` → ISO format strings
- `UUID` → string
- `Decimal` → float
- `Enum` → value
- `dataclass` → dict
- `bytes` → base64 string
- `set`, `frozenset` → list
- Custom objects with `__dict__` → dict


## Built-in Type Support

### Datetime Types

```python
from datetime import datetime, date, time
from mitsuki import RestController, GetMapping

@RestController("/api")
class EventController:
    @GetMapping("/event")
    async def get_event(self):
        return {
            "created_at": datetime.now(),  # → "2025-01-15T12:30:45.123456"
            "event_date": date.today(),     # → "2025-01-15"
            "start_time": time(14, 30)      # → "14:30:00"
        }
```

### UUID

```python
from uuid import uuid4

@RestController("/api")
class UserController:
    @GetMapping("/user")
    async def get_user(self):
        return {
            "id": uuid4(),  # → "12345678-1234-5678-1234-567812345678"
            "name": "Alice"
        }
```

### Decimal (for precise monetary values)

```python
from decimal import Decimal

@RestController("/api")
class ProductController:
    @GetMapping("/product")
    async def get_product(self):
        return {
            "name": "Widget",
            "price": Decimal("19.99")  # → 19.99 (as float)
        }
```

### Enum

```python
from enum import Enum

class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

@RestController("/api")
class OrderController:
    @GetMapping("/order")
    async def get_order(self):
        return {
            "order_id": 123,
            "status": Status.PENDING  # → "pending"
        }
```

### Dataclass

```python
from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str

@RestController("/api")
class UserController:
    @GetMapping("/user")
    async def get_user(self):
        user = User(id=1, name="Alice", email="alice@example.com")
        return user  # → {"id": 1, "name": "Alice", "email": "alice@example.com"}
```

### Collections

```python
@RestController("/api")
class TagController:
    @GetMapping("/tags")
    async def get_tags(self):
        return {
            "tags": {"python", "web", "api"}  # set → ["python", "web", "api"]
        }
```


## Basic Usage

### Automatic Serialization

Controllers automatically use Mitsuki's serialization:

```python
from datetime import datetime
from uuid import uuid4
from mitsuki import RestController, GetMapping

@RestController("/api")
class BlogController:
    @GetMapping("/post")
    async def get_post(self):
        # All special types are automatically handled
        return {
            "id": uuid4(),
            "title": "My Blog Post",
            "created_at": datetime.now(),
            "tags": {"python", "web"},
            "views": Decimal("1234.56")
        }
```

### Manual Serialization

Use `serialize_json()` for manual serialization:

```python
from mitsuki import serialize_json
from datetime import datetime

data = {
    "timestamp": datetime.now(),
    "message": "Hello"
}

json_string = serialize_json(data)
# '{"timestamp": "2025-01-15T12:30:45.123456", "message": "Hello"}'
```

### Pretty Printing

```python
from mitsuki import serialize_json

data = {"name": "Alice", "age": 30}
pretty_json = serialize_json(data, indent=2)
# {
#   "name": "Alice",
#   "age": 30
# }
```


## Custom Serializers

If the default serializer doesn't work for you, you can easily register custom serializers for your own types. In true Dependency Injection fashion, you can define a `@Provider` named `json_serializers` for it, which returns a dictionary mapping types to serializer functions:

```python
from typing import Dict, Type, Callable, Any
from mitsuki import Configuration, Provider, RestController, GetMapping

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class GeoPoint:
    def __init__(self, lat, lng):
        self.lat = lat
        self.lng = lng

@Configuration
class SerializationConfig:
    @Provider(name="json_serializers")
    def custom_serializers(self) -> Dict[Type, Callable[[Any], Any]]:
        return {
            Point: lambda p: {"x": p.x, "y": p.y},
            GeoPoint: lambda p: {"latitude": p.lat, "longitude": p.lng}
        }

@RestController("/api")
class ShapeController:
    @GetMapping("/point")
    async def get_point(self):
        return Point(10, 20)  # → {"x": 10, "y": 20}

    @GetMapping("/geopoint")
    async def get_geopoint(self):
        return GeoPoint(37.7749, -122.4194)  # → {"latitude": 37.7749, "longitude": -122.4194}
```

## Error Handling

### Safe Serialization

Use `serialize_json_safe()` to handle errors gracefully:

```python
from mitsuki import serialize_json_safe

# If serialization fails, returns {"error": "Serialization failed"}
result = serialize_json_safe(problematic_data)
```

### Production Error Handling

Mitsuki automatically uses safe serialization in production:

```python
@RestController("/api")
class DataController:
    @GetMapping("/data")
    async def get_data(self):
        # If this returns non-serializable data,
        # mitsuki returns a 500 error
        return {"data": some_complex_object}
```

## Common Patterns

### API Response with Metadata

```python
from datetime import datetime
from uuid import uuid4

@RestController("/api")
class ApiController:
    @GetMapping("/resource")
    async def get_resource(self):
        return {
            "request_id": uuid4(),
            "timestamp": datetime.now(),
            "data": {
                "items": [1, 2, 3],
                "count": 3
            },
            "meta": {
                "version": "1.0",
                "cached": False
            }
        }
```

### Nested Dataclasses

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Author:
    name: str
    email: str

@dataclass
class Article:
    title: str
    author: Author
    published_at: datetime

@GetMapping("/article")
async def get_article(self):
    author = Author(name="Alice", email="alice@example.com")
    article = Article(
        title="My Article",
        author=author,
        published_at=datetime.now()
    )
    return article
```


## Next Steps

- [Controllers](./04_controllers.md) - Build REST APIs
- [Response Entity](./09_response_entity.md) - Custom HTTP responses
- [Request/Response Validation](./10_request_response_validation.md) - Input validation
