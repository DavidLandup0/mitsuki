# Dockerizing Mitsuki Applications

Containerizing your Mitsuki application with Docker allows you to create a portable, scalable, and consistent environment for development, testing, and production.

This guide will walk you through creating a `Dockerfile` for a typical Mitsuki application.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Basic Project Structure](#basic-project-structure)
- [Creating a `.dockerignore` file](#creating-a-dockerignore-file)
- [Creating the `Dockerfile`](#creating-the-dockerfile)
- [Building the Docker Image](#building-the-docker-image)
- [Running the Docker Container](#running-the-docker-container)
- [Production-Ready `Dockerfile` (Multi-stage)](#production-ready-dockerfile-multi-stage)
- [Configuration in Docker](#configuration-in-docker)

## Prerequisites

Ensure you have Docker installed on your system. You can download it from the [official Docker website](https://www.docker.com/products/docker-desktop).

## Basic Project Structure

Let's assume your Mitsuki application has the following structure:

```
my_app/
├── app/
│   ├── __init__.py
│   ├── controllers.py
│   ├── services.py
│   └── main.py
├── application.yml
├── requirements.txt
└── Dockerfile
```

- **`app/main.py`**: Your Mitsuki application entry point.
- **`requirements.txt`**: Your Python dependencies.
- **`application.yml`**: Your base configuration file.
- **`Dockerfile`**: The file we will create.

Your `requirements.txt` should look something like this:

```txt
mitsuki
# Other dependencies like asyncpg for PostgreSQL
asyncpg
```

## Creating a `.dockerignore` file

To keep your Docker image small and speed up builds, create a `.dockerignore` file in your project root. This file tells Docker which files and directories to exclude from the build context.

For example, a `.dockerignore` could look like this:

```
# Git
.git
.gitignore

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.venv/
.env

# IDEs
.vscode/
.idea/
```

## Creating the `Dockerfile`

Here is a simple, single-stage `Dockerfile` for a Mitsuki application:


```Dockerfile
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app/main.py"]
```

**Note:** When exposing ports on Docker, you'll want to bind your application to the `0.0.0.0` host, not `localhost` or `127.0.0.1`.

If you haven't written many Dockerfiles before - a quick summary of what's being done here:

1.  **`FROM python:3.11-slim`**: Starts from a lightweight official Python 3.11 image.
2.  **`WORKDIR /app`**: Sets the default directory for subsequent commands inside the container.
3.  **`COPY requirements.txt .`**: Copies only the `requirements.txt` file first. Docker's layer caching means the `pip install` step will only be re-run if this file changes, not every time your source code changes.
4.  **`RUN pip install --no-cache-dir -r requirements.txt`**: Installs your Python dependencies. `--no-cache-dir` keeps the image size smaller.
5.  **`COPY . .`**: Copies your application source code and configuration files into the `/app` directory in the container.
6.  **`CMD ["python", "app/main.py"]`**: Specifies the command to execute when the container starts.

## Building the Docker Image

Navigate to your project root (where the `Dockerfile` is) and run the `docker build` command:

```bash
docker build -t my-mitsuki-app .
```

- **`-t my-mitsuki-app`**: Tags your image with a memorable name.
- **`.`**: Specifies the current directory as the build context.

## Running the Docker Container

Once the image is built, you can run it as a container:

```bash
docker run -p 8000:8000 --name mitsuki-container my-mitsuki-app
```

- **`-p 8000:8000`**: Maps port 8000 on your host machine to port 8000 in the container.
- **`--name mitsuki-container`**: Assigns a name to your running container for easy reference.

Your Mitsuki application should now be accessible at `http://localhost:8000`.

### Using Production Profile

It's best practice to run your containerized application with a production profile. You can set the active profile using an environment variable.

```bash
docker run -p 8000:8000 \
  -e MITSUKI_PROFILE=production \
  --name mitsuki-container \
  my-mitsuki-app
```

- **`-e MITSUKI_PROFILE=production`**: Sets the `MITSUKI_PROFILE` environment variable inside the container, which will make Mitsuki load the `application-production.yml` configuration.

## Production-Ready `Dockerfile` (Multi-stage)

For production, you would usually use a multi-stage build to create a smaller, more secure image that doesn't contain build-time dependencies. Compiled languages can also avoid storing their raw source code in the built images this way, but it's irrelevant for Python as it's an interpreted language.

Here is a more robust, multi-stage `Dockerfile`:

```Dockerfile
# --- Build Stage ---
# Use a full Python image for building dependencies that might have C extensions
FROM python:3.11 as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# --- Final Stage ---
# Use a slim image for the final, smaller image
FROM python:3.11-slim

# Create a non-root user for security
RUN useradd --create-home appuser
WORKDIR /home/appuser
USER appuser

# Copy installed packages and application code from the build stage
COPY --from=builder /app /app

# Set the working directory
WORKDIR /app

# Expose the port
EXPOSE 8000

# Run the application
CMD ["python", "app/main.py"]
```

### Why is this better for production?

1.  **Smaller Image Size**: The final image is based on `python:3.11-slim` and doesn't include the build tools and libraries that might have been needed to install dependencies in the `builder` stage.
2.  **Improved Security**:
    *   It runs the application as a **non-root user** (`appuser`), which is a critical security best practice.
    *   It contains only the necessary installed packages and code, reducing the attack surface.

## Configuration in Docker

Your application inside Docker likely needs to connect to other services like databases. Hardcoding secrets like database credentials in `application.yml` is neither secure nor flexible. The best practice is to provide them at runtime using environment variables.

Mitsuki's configuration system has a clear precedence: **YAML files > Environment Variables > Code Defaults**. For an environment variable to be used, the key must **not** be present in the loaded YAML files. For more on configuration, read [Configuration](./06_configuration.md).

**1. Omit Secrets from `application-production.yml`**

To configure the database URL via an environment variable, **remove the `url` key** from your production YAML file. This forces the framework to fall back to checking for an environment variable.

```yaml
# application-production.yml
database:
  # The 'url' key is intentionally omitted.
  # The framework will fall back to the MITSUKI_DATABASE_URL environment variable.
  pool:
    enabled: true
    size: 20

server:
  # The app must listen on 0.0.0.0 to be accessible from outside the container.
  host: 0.0.0.0
```

Your code using `@Value` will still work as expected:
```python
# e.g., in a @Configuration class
db_url: str = Value("${database.url}") # Will be populated by the env var
```