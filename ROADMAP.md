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
- Transaction support
    - I.e. `@Transactional` on `@Service`/`@Repository` methods, wrapping the unit of work in a single database transaction

### Maintenance
- Production-hardening on the core internals

## Before 0.4.0

With the completion of the features below - we go into 0.4.x versions:

### Major Features
- Entity relationships
    - I.e. `@ManyToOne`, `@OneToMany`, `@OneToOne` and `@ManyToMany` associations between `@Entity` classes
    - Eager and lazy loading modes

## Before 0.5.0

With the completion of the features below - we go into 0.5.x versions:

### Major Features
- Basic messaging/queue support

## Before 0.6.0

With the completion of the features below - we go into 0.6.x versions:

### Major Features
- Global exception handling
    - I.e. support for defining @ExceptionHandlers that handle all types of certain exceptions for centralization

## Before 0.7.0

With the completion of the features below - we go into 0.7.x versions:

### Major Features
- Testing support
    - I.e. a test application context, with overridable component registration for fakes and mocks

### Documentation
- Testing documentation

## Before 0.8.0

With the completion of the features below - we go into 0.8.x versions:

### Major Features
- Middleware API

## Before 0.9.0

With the completion of the features below - we go into 0.9.x versions:

### Major Features
- Auth/JWT support

## Before 1.0.0

### Maintenance
- Public API review and stability freeze


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