# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.2.2

### Changes
- Consolidated enum usage and replaced bare strings with enums.

### Fixes
- **During OpenAPI generation, `use_refs=False` inlines nested schemas.** `Optional`, union, `list` and `dict` members emitted a `$ref` into the schema registry instead of expanding in place.
- **`mitsuki init` URLs used to be sqlite only.** `sqlite`, `postgresql` and `mysql` all produced SQLite configuration, and now produce separate URLs properly.

## 0.2.1

### Breaking Changes
- **`UUIDv5` requires `name_field`.** Keys are derived from that field's value. They used to be derived from the class name, which is static, causing rows to share the primary key. Other `UUIDvN` variants are not affected.
- **Non-native `@Query` strings the ORM parser cannot rewrite raise `QueryException`.** They ran as raw SQL, outside the repository's entity. Use `native=True` for raw SQL.
- **`Column()` defaults follow dataclass rules.** Mutable defaults such as `Column(default=[])` raise `ValueError`.
- **`@Modifying` on a query that does not modify data raises `QueryException`.** It returned `-1`.

### Fixes
- **Omitted `Column()` fields get their declared default.**
- **ORM `@Query` strings name the repository's own entity.** `SELECT p FROM Post p` in a `User` repository returned `users` rows; it now raises `QueryException`.
- **Multipart bodies are capped while streaming.** `server.max_request_size` was checked only after the whole body was read.
- **`exclude_fields` applies to dataclasses, objects and msgspec Structs.** Only dicts were filtered.
- **Path variables bind from the URL whatever their type.** A path variable annotated as `uuid.UUID`, `date` or another non-primitive type was read from the request body.
- **`@Modifying` is required wherever a modifying statement appears.** A comment, CTE or earlier statement before the `DELETE`, `UPDATE` or `INSERT` bypassed the check.
- **Omitted `Field()` timestamps default to `None`.**
- **A non-numeric `Content-Length` no longer echoes a Python error.**

## 0.2.0

### Breaking Changes
- **Scheduler metrics configuration moved from `scheduler.metrics.*` to `metrics.*`.** `scheduler.metrics.enabled` and `scheduler.metrics.path` are no longer read.
- **The `/metrics` JSON response changed.** Scheduler statistics moved from the top level into a `scheduler` block, alongside a new `instrumentation` block.
- **Scheduler metrics require `metrics.enabled`.** With metrics disabled, scheduled executions record nothing to the metrics registry. Previously, metrics were always recorded, but `metrics.enabled` controlled whether they're exposed or not.

### Features
- **Instrumentation.** `@Instrumented()` on the `@Application` class instruments every `@Service`, `@Repository`, `@CrudRepository` and `@RestController`; on a single component it instruments only that component, and `@Instrumented(enabled=False)` opts a component out. 
- **System metrics.** Process CPU and memory are sampled while instrumentation runs. `instrumentation.track_memory` adds Python traced memory at the cost of `tracemalloc` overhead.
- **Custom metrics.** Inject `InstrumentationProvider` and call `record_metric` to count application events.
- **Prometheus endpoint.** Metrics are formatted for Prometheus and exposed at `/metrics/prometheus`, next to the human-readable `/metrics`.
- **IP allowlist.** `metrics.allowed_ips` restricts both endpoints to listed addresses and CIDR ranges.
- **Grafana dashboard.** `mitsuki grafana-dashboard` writes a ready-made dashboard for Mitsuki metrics.

### Dependencies
- **`psutil` is an optional extra.** Install `mitsuki[metrics]` to enable instrumentation. Enabling it without `psutil` fails at startup with an error naming the extra.

### Fixes
- **Implemented `@CrudRepository` methods can call the repository's declared query methods.** Implemented methods ran against an internal proxy that only had the built-in CRUD methods registered, so calling a `find_by_*` or `@Query` method from one raised `AttributeError`. They now run with the repository itself as `self`.
- **`@CrudRepository` methods are resolved once, at decoration.**
- **Component scanning no longer skips modules containing undecorated classes.** The first class without Mitsuki metadata aborted the scan of its module, leaving any components whose names sort after it unregistered.

## [0.1.5] - 2026-07-21

### Parameter Binding Bug Fixes (by virtue of adopting msgspec over custom coercion)
- **Expanded support for unannotated parameters.** such as `Optional[T]`, `List[T]`.
- **Repeated query parameters are no longer mangled.** `?tag=a&tag=b` bound to `List[str]` used to keep only the last value.
- **Body size limits hold for chunked requests.** `server.max_body_size` was only enforced when a `Content-Length` header was present, so a chunked request could bypass it entirely.
- **Type coercion failures return 400, not 500.** Failures on typing generics escaped the handler that converts them to a client error.

### Features
- **Multi-value parameters**: `List[T]` on a query parameter or form field collects every repeated value, with elements coerced to `T`.
- **Structured JSON media types**: content types with a `+json` suffix (such as `application/merge-patch+json`) are accepted for request bodies.

### Serialization
- **msgspec replaces hand-rolled type coercion and orjson.** `msgspec` now handles request decoding, validation, and response encoding. `orjson` is no longer a dependency. Response output is unchanged for every built-in type, with one improvement noted below.
- **Custom serializers now override built-in types reliably.** A serializer registered for a type Mitsuki already handles (such as `datetime`) previously applied only when the payload also contained a value that could not be encoded on the fast path, so the same handler could render a value two different ways depending on its sibling fields. Registered serializers now always take precedence, including inside lists and dataclasses and when `indent` is used.
- **`Decimal` keeps its full precision.** It was coerced to a float before encoding, so `Decimal("19.99999999999999999999")` was emitted as `20.0`. It is now written as an exact JSON number.
- **Binding is resolved at route registration.** Parameter source, field name, converter, and multi-value handling are computed once when routes are built instead of at request-time.

### Request Body Validation
Request bodies were previously validated by calling the target dataclass with the decoded JSON. Dataclasses do not type-check their arguments, so only the *presence* of fields was ever checked. `msgspec` validates the types as well, which changes four behaviours:

- **Field types are now enforced.**
- **Unknown fields are ignored rather than rejected.** A body carrying a field the DTO does not declare previously returned a 400 - incidentally, as a `TypeError` from the dataclass constructor rather than by design. Such fields are now dropped,

[0.1.5]: https://github.com/DavidLandup0/mitsuki/compare/v0.1.4...v0.1.5

## [0.1.4] - 2025-12-14

### Features
- **Request Injection**: Added the ability to inject the raw Starlette `Request` object directly into controller methods by type-hinting it.

### Documentation
- Updated the controllers documentation to include a section on accessing the raw request object.

### Improvements
- **Benchmarks**: Added Robyn and Gin (Go) to the benchmark suite for more comprehensive performance comparisons.

[0.1.4]: https://github.com/DavidLandup0/mitsuki/compare/v0.1.3...v0.1.4
## [0.1.3] - 2025-11-29

### Features
- **Alembic Integration**: Added support for database migrations through Alembic
  - `mitsuki init` now optionally generates Alembic configuration files
  - Pre-configured `env.py` template with automatic entity discovery
  - `get_sqlalchemy_metadata()` function for SQLAlchemy metadata access
  - `convert_to_async_url()` helper for converting sync database URLs to async
  - Support for profile-based configuration (MITSUKI_PROFILE environment variable) when running migrations

### Documentation
- Added database migrations guide (docs/19_database_migrations.md)
- Added live demo example of Mitsuki starters

### Improvements
- Corrected template README.md file order

[0.1.3]: https://github.com/DavidLandup0/mitsuki/releases/tag/v0.1.3

## [0.1.2] - 2025-11-28

### Features
- Refactored the CLI and project structure for a more intuitive developer experience.

### Documentation
- Added a new "Getting Started" guide for a better onboarding experience.
- Added VitePress for static-site documentation.
- Updated the main README.md and benchmarks README.md files

[0.1.2]: https://github.com/DavidLandup0/mitsuki/releases/tag/v0.1.2

## [0.1.1] - 2025-11-26

### Added
- `orjson` as a dependency instead of standard `json` library for Mitsuki's JSON encoder
- Monkey-patch for Starlette's `init_headers` function, for the common case of JSON responses with no headers

[0.1.1]: https://github.com/DavidLandup0/mitsuki/releases/tag/v0.1.1

## [0.1.0] - 2025-11-20

### Added
- Initial release of Mitsuki
- Core dependency injection container with automatic component scanning
- RESTful web framework with declarative controllers (@RestController, @GetMapping, @PostMapping, @PutMapping, @DeleteMapping)
- Service layer with @Service decorator
- Data layer with @CrudRepository and @Entity decorators
- Query DSL for automatic query generation (find_by_X, count_by_X)
- Custom queries with @Query decorator (JPQL syntax)
- @Modifying decorator for UPDATE/DELETE operations
- SQLAlchemy adapter with support for SQLite, PostgreSQL
- Request/response validation with @Produces and @Consumes decorators
- File upload support with validation (type, size limits)
- Automatic OpenAPI 3.0 specification generation
- Built-in Swagger UI, ReDoc, and Scalar documentation interfaces
- Scheduled tasks with @Scheduled decorator (cron expressions)
- Configuration management via YAML or class attributes
- CLI tool for bootstrapping new applications (mitsuki init)
- Support for multiple ASGI servers (Granian, Uvicorn, Socketify)
- Production-ready logging and metrics

[0.1.0]: https://github.com/DavidLandup0/mitsuki/releases/tag/v0.1.0