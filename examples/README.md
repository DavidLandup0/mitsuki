# Mitsuki Framework Examples

This directory contains complete, end-to-end example applications built with Mitsuki framework.
The repository of examples will eventually be expanded, with more guide-like articles accompanying the examples.

## Available Examples

### 1. Blog Application (`blog_app/`)

A full-featured blog platform demonstrating:
- Entity relationships (User, Post, Comment, Tag)
- Custom repository queries with @Query decorator
- Named and positional parameter binding
- Pagination with limit/offset
- Modifying queries (@Modifying)
- Service layer with business logic
- REST API with controllers
- Dependency injection

[View Blog App →](./blog_app/)

## Running the Examples

Each example is self-contained with its own README. To run an example:

```bash
# Navigate to the example directory
cd examples/blog_app

# Run the application
python app.py
```

### 2. Auto-Documentation Endpoints Example (`/openapi`)

A handful of basic apps, highlighting auto-documentation features.

[View Auto-Documentation Apps →](./openapi/)

### 3. @Scheduled Tasks (`/scheduled`)

Example of creating scheduled tasks to run within your app.

[View @Scheduled Example →](./scheduled/)

## Running the Examples

Each example is self-contained with its own README. To run an example:

```bash
# Navigate to the example directory
cd examples/blog_app

# Run the application
python app.py
```
