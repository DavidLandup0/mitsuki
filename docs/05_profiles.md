# Profiles - Environment-Specific Configuration

## Table of Contents

- [Overview](#overview)
- [Basic Usage](#basic-usage)
- [Profile-Specific Providers](#profile-specific-providers)
- [Configuration Files](#configuration-files)
- [Common Patterns](#common-patterns)
- [Best Practices](#best-practices)


## Overview

Profiles allow you to:
- **Conditionally register components** based on environment
- **Switch configurations** between dev, staging, production
- **Manage environment-specific providers** (databases, APIs, features)
- **Keep code clean** - No if/else for environment checks

**Key concept:** Components decorated with `@Profile` only register when that profile is active.

## Basic Usage

### Setting the Active Profile

Set the `MITSUKI_PROFILE` environment variable:

```bash
# Development
MITSUKI_PROFILE=development python app.py

# Staging
MITSUKI_PROFILE=staging python app.py

# Production
MITSUKI_PROFILE=production python app.py
```

**Default profile:** If `MITSUKI_PROFILE` is not set, defaults to `"default"`

### Single Profile

```python
from mitsuki import Configuration, Profile, Provider

@Configuration
@Profile("development")
class DevelopmentConfig:
    @Provider
    def database_url(self) -> str:
        return "sqlite:///dev.db"

    @Provider
    def debug_mode(self) -> bool:
        return True
```

**Behavior:**
- Active when `MITSUKI_PROFILE=development`
- Inactive for any other profile
- Providers only registered when profile is active

### Multiple Profiles

A component can be active for multiple profiles (OR logic):

```python
@Configuration
@Profile("development", "test")
class NonProductionConfig:
    @Provider
    def api_timeout(self) -> int:
        return 30  # Short timeout for dev/test
```

**Behavior:**
- Active when `MITSUKI_PROFILE=development` OR `MITSUKI_PROFILE=test`
- Inactive for production or other profiles


## Profile-Specific Providers

### Database Configuration

```python
from mitsuki import Configuration, Profile, Provider

@Configuration
@Profile("development")
class DevDatabaseConfig:
    @Provider
    def database_url(self) -> str:
        return "sqlite:///dev.db"

    @Provider
    def database_pool_size(self) -> int:
        return 5

@Configuration
@Profile("production")
class ProdDatabaseConfig:
    @Provider
    def database_url(self) -> str:
        return "postgresql://prod-server:5432/app_db"

    @Provider
    def database_pool_size(self) -> int:
        return 50
```

**Usage in services:**
```python
@Service()
class DatabaseService:
    def __init__(self, database_url: str, database_pool_size: int):
        # Gets dev or prod values based on active profile
        self.url = database_url
        self.pool_size = database_pool_size
```

### API Configuration

```python
@Configuration
@Profile("development")
class DevApiConfig:
    @Provider
    def api_base_url(self) -> str:
        return "http://localhost:3000"

    @Provider
    def api_timeout(self) -> int:
        return 10

    @Provider
    def api_retry_count(self) -> int:
        return 1

@Configuration
@Profile("production")
class ProdApiConfig:
    @Provider
    def api_base_url(self) -> str:
        return "https://api.production.com"

    @Provider
    def api_timeout(self) -> int:
        return 60

    @Provider
    def api_retry_count(self) -> int:
        return 3
```

### Feature Flags

```python
@Configuration
@Profile("development", "staging")
class BetaFeaturesConfig:
    @Provider
    def enable_new_ui(self) -> bool:
        return True

    @Provider
    def enable_analytics(self) -> bool:
        return False

@Configuration
@Profile("production")
class ProductionFeaturesConfig:
    @Provider
    def enable_new_ui(self) -> bool:
        return False  # Disabled in prod

    @Provider
    def enable_analytics(self) -> bool:
        return True
```


## Configuration Files

### Profile-Specific YAML Files

Create separate configuration files per environment:

```
project/
├── application.yml              # Base configuration
├── application-development.yml  # Dev overrides
├── application-staging.yml      # Staging overrides
└── application-production.yml   # Production overrides
```

**application.yml (base):**
```yaml
server:
  host: 0.0.0.0
  port: 8000

logging:
  level: INFO
```

**application-development.yml:**
```yaml
database:
  url: sqlite:///dev.db
  echo: true  # Show SQL queries

logging:
  level: DEBUG

app:
  debug: true
```

**application-production.yml:**
```yaml
database:
  url: postgresql://prod-server/db
  echo: false

logging:
  level: WARNING

app:
  debug: false
```

### Accessing Configuration

```python
from mitsuki import Configuration, Value

@Configuration
class AppConfig:
    # Values automatically loaded from application-{profile}.yml
    database_url: str = Value("${database.url}")
    debug_mode: bool = Value("${app.debug:false}")
    log_level: str = Value("${logging.level:INFO}")
```


## Common Patterns

### Pattern 1: Database Per Environment

```python
@Configuration
@Profile("development")
class DevDatabase:
    @Provider
    def db_connection(self) -> str:
        return "sqlite:///dev.db"

@Configuration
@Profile("test")
class TestDatabase:
    @Provider
    def db_connection(self) -> str:
        return "sqlite:///:memory:"  # In-memory for tests

@Configuration
@Profile("production")
class ProdDatabase:
    @Provider
    def db_connection(self) -> str:
        return "postgresql://prod/db"
```

### Pattern 2: Mock Services in Development

```python
@Service()
@Profile("production")
class RealEmailService:
    async def send_email(self, to: str, subject: str, body: str):
        # Actually send email via SMTP
        pass

@Service()
@Profile("development", "test")
class MockEmailService:
    async def send_email(self, to: str, subject: str, body: str):
        # Just log, don't actually send
        print(f"MOCK EMAIL: To={to}, Subject={subject}")
```

Both services have the same interface, so code using EmailService doesn't need to change:

```python
@Service()
class UserService:
    def __init__(self, email_service: EmailService):
        # Gets real or mock based on profile
        self.email = email_service

    async def register_user(self, email: str):
        await self.email.send_email(
            to=email,
            subject="Welcome!",
            body="Thanks for registering"
        )
```

### Pattern 3: Feature Toggles

```python
@Configuration
class FeatureConfig:
    @Provider
    @Profile("development", "staging")
    def beta_features_enabled(self) -> bool:
        return True

    @Provider
    @Profile("production")
    def beta_features_enabled(self) -> bool:
        return False

@Service()
class FeatureService:
    def __init__(self, beta_features_enabled: bool):
        self.beta_enabled = beta_features_enabled

    async def get_features(self) -> List[str]:
        features = ["core_feature_1", "core_feature_2"]

        if self.beta_enabled:
            features.extend(["beta_feature_1", "beta_feature_2"])

        return features
```

### Pattern 4: External Service Configuration

```python
@Configuration
@Profile("development")
class DevExternalServices:
    @Provider
    def payment_api_url(self) -> str:
        return "https://sandbox.stripe.com"

    @Provider
    def payment_api_key(self) -> str:
        return "sk_test_..."

@Configuration
@Profile("production")
class ProdExternalServices:
    @Provider
    def payment_api_url(self) -> str:
        return "https://api.stripe.com"

    @Provider
    def payment_api_key(self) -> str:
        # In production, use environment variable
        import os
        return os.getenv("STRIPE_API_KEY")
```

### Pattern 5: Logging Configuration

```python
@Configuration
@Profile("development")
class DevLogging:
    @Provider
    def log_level(self) -> str:
        return "DEBUG"

    @Provider
    def log_sql_queries(self) -> bool:
        return True

    @Provider
    def log_requests(self) -> bool:
        return True

@Configuration
@Profile("production")
class ProdLogging:
    @Provider
    def log_level(self) -> str:
        return "WARNING"

    @Provider
    def log_sql_queries(self) -> bool:
        return False

    @Provider
    def log_requests(self) -> bool:
        return False
```


## Complete Example

```python
from mitsuki import Application, Configuration, Profile, Provider, Service
from mitsuki import RestController, GetMapping, Value

# Shared base configuration
@Configuration
class BaseConfig:
    app_name: str = Value("${app.name:Mitsuki App}")

    @Provider
    def max_upload_size(self) -> int:
        return 10 * 1024 * 1024  # 10MB

# Development configuration
@Configuration
@Profile("development")
class DevelopmentConfig:
    @Provider
    def database_url(self) -> str:
        return "sqlite:///dev.db"

    @Provider
    def api_timeout(self) -> int:
        return 10

    @Provider
    def enable_debug_toolbar(self) -> bool:
        return True

# Staging configuration
@Configuration
@Profile("staging")
class StagingConfig:
    @Provider
    def database_url(self) -> str:
        return "postgresql://staging-db:5432/app"

    @Provider
    def api_timeout(self) -> int:
        return 30

    @Provider
    def enable_debug_toolbar(self) -> bool:
        return True

# Production configuration
@Configuration
@Profile("production")
class ProductionConfig:
    @Provider
    def database_url(self) -> str:
        import os
        return os.getenv("DATABASE_URL", "postgresql://prod-db:5432/app")

    @Provider
    def api_timeout(self) -> int:
        return 60

    @Provider
    def enable_debug_toolbar(self) -> bool:
        return False

# Service using configuration
@Service()
class ConfigService:
    def __init__(
        self,
        database_url: str,
        api_timeout: int,
        enable_debug_toolbar: bool,
        max_upload_size: int
    ):
        self.database_url = database_url
        self.api_timeout = api_timeout
        self.debug_toolbar = enable_debug_toolbar
        self.max_upload = max_upload_size

    def get_config_info(self) -> dict:
        return {
            "database_url": self.database_url,
            "api_timeout": self.api_timeout,
            "debug_toolbar": self.debug_toolbar,
            "max_upload_size": self.max_upload
        }

# Controller exposing configuration
@RestController("/api/config")
class ConfigController:
    def __init__(self, service: ConfigService):
        self.service = service

    @GetMapping("")
    async def get_config(self) -> dict:
        import os
        return {
            "profile": os.getenv("MITSUKI_PROFILE", "default"),
            "config": self.service.get_config_info()
        }

# Application
@Application
class MyApp:
    port: int = Value("${server.port:8000}")

if __name__ == "__main__":
    import os
    print(f"Starting with profile: {os.getenv('MITSUKI_PROFILE', 'default')}")
    MyApp.run()
```

**Running:**
```bash
# Development
MITSUKI_PROFILE=development python app.py

# Staging
MITSUKI_PROFILE=staging python app.py

# Production
DATABASE_URL=postgresql://prod/db MITSUKI_PROFILE=production python app.py
```


## Best Practices

1. **Use profiles for environment differences** - Not for feature flags in same environment
2. **Keep profile names consistent** - Standard: development, staging, production
3. **Don't commit secrets** - Use environment variables in production profile
4. **Provide sensible defaults** - Use `@Value` with defaults
5. **Document required environment variables** - For each profile
6. **Use @Profile on @Configuration classes** - Not on individual services
7. **Test with each profile** - Ensure all profiles work
8. **Combine profiles for testing** - e.g., "development, test"
9. **Use profile-specific YAML files** - For complex configuration
10. **Keep development simple** - SQLite, mock services, verbose logging


## Profile Detection

Check active profile at runtime:

```python
import os

def get_active_profile() -> str:
    return os.getenv("MITSUKI_PROFILE", "default")

def is_production() -> bool:
    return get_active_profile() == "production"

def is_development() -> bool:
    return get_active_profile() == "development"
```


## Troubleshooting

### Profile not activating

**Check:**
1. Environment variable is set: `echo $MITSUKI_PROFILE`
2. Profile name matches exactly (case-sensitive)
3. Configuration class is imported (so decorator runs)

### Wrong providers registered

**Check:**
1. Multiple configurations with same provider names
2. Last registered provider wins if names conflict
3. Use unique provider names or proper profile separation

### Profile-specific config file not loaded

**Check:**
1. File named correctly: `application-{profile}.yml`
2. File in correct location (project root)
3. YAML syntax is valid


## Next Steps

- [Configuration](./06_configuration.md) - Complete configuration guide
- [Decorators](./02_decorators.md) - All decorators reference
- [Overview](./01_overview.md) - Framework architecture
