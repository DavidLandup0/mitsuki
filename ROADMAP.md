# Mitsuki Roadmap

## Before 0.2.0

With the completion of the features below - we go into 0.2.x versions:

### Major Features
- Instrumentation support
    - Adding @Instrumented, to automatically instrument an @Application and its @Components.
    - Consolidate/unify @Scheduled metrics with @Instrumented metrics
    - Add core metric collection support
    - Support for Prometheus format metrics for scraping/ingestion
- Alembic support
    - Support through both the CLI init and connecting the DB with Alembic for easy migrations

### Minor Features
- Request injection in controllers
    - I.e. support injecting a `request: Request` into controllers


### Documentation
- Examples of aggregating Prometheus data with Grafana
- Documentation on Instrumentation capabilities
- Documentation on limiting /metrics access

## Before 0.3.0

With the completion of the features below - we go into 0.3.x versions:

### Major Features
- Basic messaging/queue support
- Global exception handling
    - I.e. support for defining @ExceptionHandlers that handle all types of certain exceptions for centralization

### Maintenance
- Production-hardening on the core internals


## Overarching

I.e. items not necessarily tied to a single version.

### Maintenance

This is a weekend project, worked on by a single engineer, some coffee and Claude Code.
Directing AI models to do proper engineering is non-trivial, as they're still deeply misaligned with good engineering practices.

Moving from the early stages (right now) to more stable, hardened stages will require refactoring, rewriting, etc.
This section is dedicated to that move:

- Clean up the AI-induced sloppiness introduced in early iterations
    - ... it works, but it's sloppy.
    - Consolidate metadata usage, naming and checks within components
    - Remove unnecessary/overly safe checks which don't actually add value
    - Lots of if-else shennanigans - formalize method signatures, register dictionaries matching types to functions
    - etc.