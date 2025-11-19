# Configuration & Providers

## Table of Contents

- [Overview](#overview)
- [Configuration Files](#configuration-files)
- [@Value Injection](#value-injection)
- [@Configuration Classes](#configuration-classes)
- [@Provider Factory Methods](#provider-factory-methods)
- [Environment Variables](#environment-variables)
- [Configuration Source Logging](#configuration-source-logging)
- [Complete Examples](#complete-examples)


## Overview

Mitsuki provides multiple ways to configure your application:

1. **application.yml** - Primary configuration file
2. **Environment variables** - Override YAML values
3. **@Value injection** - Inject config into components
4. **@Provider factory methods** - Create configured objects
5. **Profile-specific files** - Different configs per environment

**NOTE:** Mitsuki has a `defaults.yml` file, which provides default configs for most components. They're used when you don't set any higher level of configuration.

## Configuration Files

### application.yml

Create `application.yml` in your project root:

```yaml
# Server configuration
server:
  host: 0.0.0.0
  port: 8000
  type: granian  # Options: uvicorn, granian
  timeout: 60  # Request timeout in seconds (optional)
  max_body_size: 10485760  # 10MB in bytes
  ignore_trailing_slash: true
  cors:
    enabled: false 
    allowed_origins:
      - "*"

# Database configuration
database:
  url: sqlite:///mitsuki_app.db
  adapter: sqlalchemy
  echo: false

# Application settings
app:
  name: My Mitsuki Application
  debug: false
  max_upload_size: 10485760  # 10MB

# Logging
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  sqlalchemy: false

# Custom settings
email:
  smtp_host: smtp.gmail.com
  smtp_port: 587
  from_address: noreply@example.com

api:
  timeout: 30
  retry_count: 3
  base_url: https://api.example.com
```

### Nested Configuration

Access nested values with dot notation:

```yaml
database:
  connection:
    pool:
      size: 10
      timeout: 30
    retry:
      max_attempts: 3
      backoff: 1000
```

```python
pool_size: int = Value("${database.connection.pool.size}")
max_attempts: int = Value("${database.connection.retry.max_attempts}")
```

### Profile-Specific Files

Create environment-specific configuration:

```
defaults.yml                     # Mitsuki-level defaults - overriden by any configs
project/
├── application.yml              # Base (all environments)
├── application-development.yml  # Development overrides
├── application-test.yml         # Test overrides
├── application-staging.yml      # Staging overrides
└── application-production.yml   # Production overrides
```

#TODO is this accurate?
When `MITSUKI_PROFILE=production`, Mitsuki loads:
1. `application.yml` (base)
2. `application-production.yml` (overrides)


## @Value Injection

Inject configuration values into class properties using `@Value`.

### Basic Injection

```python
from mitsuki import Configuration, Value

@Configuration
class AppConfig:
    # Simple value injection
    app_name: str = Value("${app.name}")

    # With default value
    port: int = Value("${server.port:8000}")

    # Nested configuration
    pool_size: int = Value("${database.connection.pool.size:10}")
```

### Syntax

**${key}** - Get value for key, None if not found:
```python
app_name: str = Value("${app.name}")
```

**${key:default}** - Get value for key, use default if not found:
```python
port: int = Value("${server.port:8000}")
debug: bool = Value("${app.debug:false}")
```

### Type Conversion

Mitsuki automatically converts values to the correct type:

```python
@Configuration
class AppConfig:
    # Integer
    port: int = Value("${server.port:8000}")

    # Float
    timeout: float = Value("${api.timeout:30.5}")

    # Boolean
    debug: bool = Value("${app.debug:false}")  # "true", "yes" -> True
    enabled: bool = Value("${feature.enabled:true}")

    # String
    app_name: str = Value("${app.name:My App}")
```

### Using in Services

```python
from mitsuki import Service, Value

@Service()
class EmailService:
    smtp_host: str = Value("${email.smtp_host}")
    smtp_port: int = Value("${email.smtp_port:587}")
    from_address: str = Value("${email.from_address}")

    async def send_email(self, to: str, subject: str, body: str):
        # Use injected configuration
        print(f"Sending via {self.smtp_host}:{self.smtp_port}")
```

### Using in @Application

```python
from mitsuki import Application, Value

@Application
class MyApp:
    # Inject configuration directly into application class
    port: int = Value("${server.port:8000}")
    host: str = Value("${server.host:127.0.0.1}")

if __name__ == "__main__":
    MyApp.run()  # Uses injected port value
```


## @Configuration Classes

Configuration classes organize related configuration and provider definitions.

### Basic Configuration Class

```python
from mitsuki import Configuration, Value

@Configuration
class DatabaseConfig:
    # Configuration properties
    url: str = Value("${database.url}")
    pool_size: int = Value("${database.pool.size:10}")
    echo: bool = Value("${database.echo:false}")
```

### Injecting Configuration

Configuration classes can be injected into services:

```python
@Service()
class DatabaseService:
    def __init__(self, config: DatabaseConfig):
        self.config = config

    async def connect(self):
        print(f"Connecting to {self.config.url}")
        print(f"Pool size: {self.config.pool_size}")
```

### Configuration with Dependencies

Configuration classes can have dependencies:

```python
@Service()
class SecretManager:
    def get_secret(self, key: str) -> str:
        # Fetch from vault, AWS Secrets Manager, etc.
        return "secret-value"

@Configuration
class ApiConfig:
    def __init__(self, secrets: SecretManager):
        self.secrets = secrets

    @Provider
    def api_key(self) -> str:
        # Use injected service to get secret
        return self.secrets.get_secret("api_key")
```


## @Provider Factory Methods

Provider factory methods create and configure complex objects.

### Basic Provider

```python
from mitsuki import Configuration, Provider
import httpx

@Configuration
class HttpClientConfig:
    @Provider
    def http_client(self) -> httpx.AsyncClient:
        """Create configured HTTP client"""
        return httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "Mitsuki/1.0"}
        )
```

### Provider with Configuration

```python
@Configuration
class HttpClientConfig:
    timeout: int = Value("${http.timeout:30}")
    base_url: str = Value("${http.base_url}")

    @Provider
    def http_client(self) -> httpx.AsyncClient:
        """Create client using configuration values"""
        return httpx.AsyncClient(
            timeout=self.timeout,
            base_url=self.base_url
        )
```

### Multiple Providers

```python
@Configuration
class ClientConfig:
    @Provider
    def internal_api_client(self) -> httpx.AsyncClient:
        """Client for internal API"""
        return httpx.AsyncClient(
            timeout=10,
            base_url="http://internal-api:8080"
        )

    @Provider
    def external_api_client(self) -> httpx.AsyncClient:
        """Client for external API"""
        return httpx.AsyncClient(
            timeout=60,
            base_url="https://api.external.com"
        )

    @Provider
    def payment_client(self) -> httpx.AsyncClient:
        """Client for payment gateway"""
        return httpx.AsyncClient(
            timeout=120,
            base_url="https://payment-gateway.com"
        )
```

### Provider Injection

Providers are injected by parameter name:

```python
@Service()
class ApiService:
    def __init__(
        self,
        internal_api_client: httpx.AsyncClient,
        external_api_client: httpx.AsyncClient
    ):
        # Providers matched by parameter name
        self.internal_client = internal_api_client
        self.external_client = external_api_client

    async def fetch_internal_data(self):
        return await self.internal_client.get("/data")

    async def fetch_external_data(self):
        return await self.external_client.get("/data")
```

### Custom Provider Names

```python
@Configuration
class Config:
    @Provider(name="primary_db")
    def create_primary_connection(self) -> str:
        return "postgresql://primary/db"

    @Provider(name="replica_db")
    def create_replica_connection(self) -> str:
        return "postgresql://replica/db"

@Service()
class DatabaseService:
    def __init__(self, primary_db: str, replica_db: str):
        # Matched by custom provider names
        self.primary = primary_db
        self.replica = replica_db
```

### Provider Scopes

```python
@Configuration
class Config:
    @Provider(scope="singleton")  # Default - one instance
    def connection_pool(self) -> ConnectionPool:
        return ConnectionPool(size=10)

    @Provider(scope="prototype")  # New instance each time (limited support)
    def temp_file(self) -> TempFile:
        return TempFile()
```

**Note:** For `@Provider` factory methods, prototype scope currently has limitations. The factory method runs once during initialization.


## Environment Variables

### Fallback Configuration

Environment variables serve as **fallback** values when a key isn't defined in `application.yml` or profile-specific files. This is useful for containerized deployments or CI/CD where modifying config files isn't practical.

```bash
# Provide fallback for ${server.port} if not in application.yml
MITSUKI_SERVER_PORT=9000 python app.py

# Provide fallback for ${database.url}
MITSUKI_DATABASE_URL=postgresql://localhost/db python app.py

# Provide fallback for ${app.debug}
MITSUKI_APP_DEBUG=true python app.py
```

**Note:** If the key exists in `application.yml` or `application-{profile}.yml`, those values take precedence over environment variables.

**Naming convention:**
- Prefix: `MITSUKI_`
- Convert dots to underscores: `server.port` → `SERVER_PORT`
- Uppercase: `MITSUKI_SERVER_PORT`

### Direct Environment Variables

Read environment variables directly:

```python
import os

@Configuration
class Config:
    @Provider
    def api_key(self) -> str:
        # Read directly from environment
        return os.getenv("API_KEY", "default-key")

    @Provider
    def database_url(self) -> str:
        # Different variable names per environment
        if os.getenv("MITSUKI_PROFILE") == "production":
            return os.getenv("PROD_DATABASE_URL")
        else:
            return "sqlite:///dev.db"
```


## Configuration Source Logging

Mitsuki can log where each configuration value is loaded from, helping you debug configuration issues and understand which values are being overridden.

### Enable Configuration Source Logging

Add to your `application.yml`:

```yaml
logging:
  log_config_sources: true
```

### Output Format

When enabled, Mitsuki displays a color-coded table during startup showing all configuration keys grouped by their source:

```
Configuration sources:

[default configuration]
┌──────────────────────────────────────────────────────────────────────┐
│database.adapter              database.echo                           │
│database.pool.enabled         database.pool.max_overflow              │
│database.pool.recycle         database.pool.size                      │
│database.pool.timeout         logging.format                          │
│logging.sqlalchemy            server.cors.allowed_origins             │
│server.max_body_size          server.multipart.max_file_size          │
│server.multipart.max_request_size  server.workers                     │
└──────────────────────────────────────────────────────────────────────┘

[application.yml]
┌──────────────────────────────────────────────────────────────────────┐
│logging.level                 logging.log_config_sources              │
│server.access_log             server.cors.enabled                     │
│server.ignore_trailing_slash  server.type                             │
└──────────────────────────────────────────────────────────────────────┘

[environment variable (MITSUKI_SERVER_PORT)]
┌──────────────────────────────────────────────────────────────────────┐
│server.port                                                            │
└──────────────────────────────────────────────────────────────────────┘
```

### Configuration Sources

Mitsuki tracks configuration from four sources (in order of priority, highest to lowest):

1. **Profile-specific files** - `application-{profile}.yml` (highest priority)
2. **Application file** - `application.yml`
3. **Environment variables** - `MITSUKI_*` prefixed environment variables (fallback)
4. **Default configuration** - Framework defaults from `mitsuki/config/defaults.yml`

This priority ensures your configuration files are the source of truth, with environment variables serving as a fallback for containerized deployments or CI/CD environments where file modification isn't practical.

### Use Cases

Configuration source logging is useful for:

- **Debugging** - See which file is providing each value
- **Environment verification** - Confirm environment variables are being applied
- **Configuration auditing** - Understand the complete configuration state
- **Troubleshooting overrides** - Identify why a value differs from expectations

### Programmatic Access

You can also access configuration sources programmatically:

```python
from mitsuki.config import get_config

config = get_config()
sources = config.get_config_sources()

for key, source in sources.items():
    print(f"{key} loaded from {source}")
```

### Security Note

Configuration source logging **does not** display configuration values, only the keys and their sources. This prevents accidentally logging sensitive information like passwords, API keys, or secrets.


## Complete Examples

### Application with Full Configuration

```python
from mitsuki import Application, Configuration, Provider, Service, Value
from mitsuki import RestController, GetMapping
import httpx

# 1. Base configuration
@Configuration
class AppConfig:
    app_name: str = Value("${app.name:Mitsuki App}")
    version: str = Value("${app.version:1.0.0}")
    debug: bool = Value("${app.debug:false}")

# 2. Database configuration
@Configuration
class DatabaseConfig:
    url: str = Value("${database.url:sqlite:///app.db}")
    pool_size: int = Value("${database.pool.size:10}")
    pool_timeout: int = Value("${database.pool.timeout:30}")

    @Provider
    def connection_string(self) -> str:
        """Build complete connection string with pool settings"""
        return f"{self.url}?pool_size={self.pool_size}&timeout={self.pool_timeout}"

# 3. HTTP client configuration
@Configuration
class HttpConfig:
    timeout: int = Value("${http.timeout:30}")
    max_retries: int = Value("${http.max_retries:3}")
    base_url: str = Value("${http.base_url:https://api.example.com}")

    @Provider
    def http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout,
            base_url=self.base_url,
            headers={"User-Agent": "Mitsuki/1.0"}
        )

# 4. Service using configuration
@Service()
class ApiService:
    def __init__(
        self,
        app_config: AppConfig,
        http_client: httpx.AsyncClient
    ):
        self.config = app_config
        self.client = http_client

    async def fetch_data(self):
        response = await self.client.get("/data")
        return response.json()

# 5. Controller
@RestController("/api")
class ApiController:
    def __init__(self, service: ApiService):
        self.service = service

    @GetMapping("/data")
    async def get_data(self) -> dict:
        return await self.service.fetch_data()

    @GetMapping("/info")
    async def get_info(self) -> dict:
        return {
            "app_name": self.service.config.app_name,
            "version": self.service.config.version,
            "debug": self.service.config.debug
        }

# 6. Application
@Application
class MyApp:
    port: int = Value("${server.port:8000}")

if __name__ == "__main__":
    MyApp.run()
```

**application.yml:**
```yaml
app:
  name: My Application
  version: 1.0.0
  debug: false

server:
  port: 8000

database:
  url: sqlite:///app.db
  pool:
    size: 10
    timeout: 30

http:
  timeout: 30
  max_retries: 3
  base_url: https://api.example.com
```

### Multi-Environment Configuration

```python
from mitsuki import Configuration, Profile, Provider, Value
import os

# Shared configuration
@Configuration
class SharedConfig:
    app_name: str = Value("${app.name}")
    max_upload_size: int = Value("${app.max_upload:10485760}")

# Development
@Configuration
@Profile("development")
class DevConfig:
    @Provider
    def database_url(self) -> str:
        return "sqlite:///dev.db"

    @Provider
    def log_level(self) -> str:
        return "DEBUG"

    @Provider
    def enable_debug_toolbar(self) -> bool:
        return True

# Production
@Configuration
@Profile("production")
class ProdConfig:
    @Provider
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", "postgresql://localhost/prod")

    @Provider
    def log_level(self) -> str:
        return "WARNING"

    @Provider
    def enable_debug_toolbar(self) -> bool:
        return False

@Service()
class ConfigService:
    def __init__(
        self,
        shared: SharedConfig,
        database_url: str,
        log_level: str,
        enable_debug_toolbar: bool
    ):
        self.app_name = shared.app_name
        self.max_upload = shared.max_upload_size
        self.db_url = database_url
        self.log_level = log_level
        self.debug_toolbar = enable_debug_toolbar
```


## Best Practices

1. **Use @Value for simple config** - Strings, numbers, booleans
2. **Use @Provider for complex objects that are reusable** - HTTP clients, connection pools
3. **Group related configuration** - One @Configuration per concern
4. **Provide defaults** - Use `${key:default}` syntax
5. **Don't commit secrets** - Use environment variables for sensitive data
6. **Use profiles for environments** - Different configs per environment


## Configuration Validation

```python
@Configuration
class ValidatedConfig:
    database_url: str = Value("${database.url}")
    api_key: str = Value("${api.key}")

    def __post_init__(self):
        """Validate configuration after injection"""
        if not self.database_url:
            raise ValueError("database.url is required")
```


## Next Steps

- [Profiles](./05_profiles.md) - Environment-specific configuration
- [Decorators](./02_decorators.md) - Complete decorator reference
- [Overview](./01_overview.md) - Framework architecture
