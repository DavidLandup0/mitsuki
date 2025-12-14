"""
Mitsuki - Spring-inspired Python web framework.
Enterprise-grade annotation-driven development for Python.
"""

# Core
# Config
from mitsuki.config import Profile, Value
from mitsuki.core.application import Application, ApplicationContext
from mitsuki.core.container import DIContainer, get_container
from mitsuki.core.decorators import (
    Component,
    Configuration,
    Provider,
    Repository,
    Scheduled,
    Service,
)
from mitsuki.core.enums import (
    ASGIMessageType,
    ASGIScopeType,
    DatabaseAdapter,
    DatabaseDialect,
    ParameterKind,
    Scope,
    ServerType,
    SQLOperation,
)

# Logging
from mitsuki.core.logging import get_logger
from mitsuki.core.utils import get_active_profile

# Data
from mitsuki.data import (
    UUID,
    Column,
    CrudRepository,
    Entity,
    Field,
    Id,
    Modifying,
    Query,
    UUIDv1,
    UUIDv4,
    UUIDv5,
    UUIDv7,
)

# Web
from mitsuki.web.controllers import Controller, RestController, RestRouter, Router
from mitsuki.web.mappings import (
    Consumes,
    Delete,
    DeleteMapping,
    Get,
    GetMapping,
    Patch,
    PatchMapping,
    Post,
    PostMapping,
    Produces,
    Put,
    PutMapping,
    RequestMapping,
)
from mitsuki.web.params import (
    FormFile,
    FormParam,
    PathVariable,
    QueryParam,
    RequestBody,
    RequestHeader,
    RequestParam,
)
from mitsuki.web.response import JSONResponse, JsonResponse, ResponseEntity
from mitsuki.web.serialization import (
    serialize_json,
    serialize_json_safe,
)
from mitsuki.web.upload import UploadFile

__version__ = "0.1.4"
__all__ = [
    # Core
    "Application",
    "ApplicationContext",
    "Component",
    "Service",
    "Repository",
    "Configuration",
    "Provider",
    "Scheduled",
    "DIContainer",
    "get_container",
    "get_active_profile",
    # Enums
    "ServerType",
    "DatabaseAdapter",
    "DatabaseDialect",
    "SQLOperation",
    "ASGIMessageType",
    "ASGIScopeType",
    "ParameterKind",
    "Scope",
    # Logging
    "get_logger",
    # Web
    "Controller",
    "RestController",
    "Router",
    "RestRouter",
    "GetMapping",
    "PostMapping",
    "PutMapping",
    "DeleteMapping",
    "PatchMapping",
    "RequestMapping",
    "Produces",
    "Consumes",
    "Get",
    "Post",
    "Put",
    "Delete",
    "Patch",
    "PathVariable",
    "QueryParam",
    "RequestParam",
    "RequestBody",
    "RequestHeader",
    "FormFile",
    "FormParam",
    "UploadFile",
    "ResponseEntity",
    "JsonResponse",
    "JSONResponse",
    # Data
    "Entity",
    "CrudRepository",
    "Id",
    "Column",
    "Field",
    "UUID",
    "UUIDv1",
    "UUIDv4",
    "UUIDv5",
    "UUIDv7",
    "Query",
    "Modifying",
    # Config
    "Value",
    "Profile",
    # Serialization
    "serialize_json",
    "serialize_json_safe",
]
