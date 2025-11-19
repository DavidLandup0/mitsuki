# Logging

Mitsuki provides built-in logging with customization support.

## Default Logging

By default, Mitsuki uses console logging with the following configuration:

```yaml
# application.yml
logging:
  level: INFO
  format: "%(levelname)s %(message)s"
  sqlalchemy: false
```

**Log levels:**
- `DEBUG` - Cyan
- `INFO` - Green
- `WARNING` - Yellow
- `ERROR` - Red
- `CRITICAL` - Magenta

## Configuration Options

### Log Level

Set the minimum log level:

```yaml
logging:
  level: DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Log Format

Customize the log message format:

```yaml
logging:
  format: "%(asctime)s %(levelname)s %(message)s"
```

Standard Python logging format specifiers are supported.

### SQLAlchemy Query Logging

Enable database query logging:

```yaml
logging:
  sqlalchemy: true
```

When enabled, all SQL queries will be logged at INFO level.

## Custom Logging

You can provide custom logging formatters and handlers using a, you guessed it, `@Provider`.

### Custom Formatter

When a `log_formatter` is injected as a component into the container - Mitsuki will pick it up and use it instead of the default logger:

```python
import logging
from mitsuki import Configuration, Provider

@Configuration
class LoggingConfig:
    @Provider(name="log_formatter")
    def custom_formatter(self) -> logging.Formatter:
        return logging.Formatter(
            fmt="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
```

### Custom Handlers

```python
import logging
from typing import List
from mitsuki import Configuration, Provider

@Configuration
class LoggingConfig:
    @Provider(name="log_handlers")
    def custom_handlers(self) -> List[logging.Handler]:
        # File handler
        file_handler = logging.FileHandler("app.log")
        file_handler.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        return [file_handler, console_handler]
```

### Both Formatter and Handlers

```python
import logging
from typing import List
from mitsuki import Configuration, Provider

@Configuration
class LoggingConfig:
    @Provider(name="log_formatter")
    def custom_formatter(self) -> logging.Formatter:
        return logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    @Provider(name="log_handlers")
    def custom_handlers(self, log_formatter: logging.Formatter) -> List[logging.Handler]:
        file_handler = logging.FileHandler("app.log")
        file_handler.setFormatter(log_formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)

        return [file_handler, console_handler]
```

## Using the Logger

You can also import the default Mitsuki logger if you'd like:

```python
from mitsuki.core.logging import get_logger

logger = get_logger()

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
```

The logger is automatically configured based on your `application.yml` settings and custom providers.

## Example: JSON Logging

```python
import logging
import json
from typing import List
from mitsuki import Configuration, Provider

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        return json.dumps(log_obj)

@Configuration
class LoggingConfig:
    @Provider(name="log_formatter")
    def json_formatter(self) -> logging.Formatter:
        return JsonFormatter()
```

### Access Logs

Enable or disable HTTP access logs:

```yaml
server:
  access_log: true  # Enable access logs
```

Access logs show incoming HTTP requests:
```
INFO GET /api/users 200 OK
INFO POST /api/users 201 Created
```

## Notes

- Custom formatters override the default `ColoredFormatter`
- Custom handlers override the default `StreamHandler`
- The `log_formatter` and `log_handlers` provider names are reserved for logging configuration
