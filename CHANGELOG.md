# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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