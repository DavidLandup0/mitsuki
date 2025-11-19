import logging
import sys
from typing import Any, Dict, List, Optional

_mitsuki_logger: Optional[logging.Logger] = None


class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            levelname_color = (
                f"{self.COLORS[levelname]}{self.BOLD}{levelname:<8}{self.RESET}"
            )
            record.levelname = levelname_color
        return super().format(record)


def get_logger() -> logging.Logger:
    """
    Get the Mitsuki logger.
    Returns a logger instance configured according to application.yml settings.
    """
    global _mitsuki_logger
    if _mitsuki_logger is None:
        _mitsuki_logger = logging.getLogger("mitsuki")
    return _mitsuki_logger


def configure_logging(
    level: str = "INFO",
    format: str = "%(levelname)s %(message)s",
    sqlalchemy: bool = False,
    custom_formatter: Optional[logging.Formatter] = None,
    custom_handlers: Optional[List[logging.Handler]] = None,
):
    """
    Configure logging for the Mitsuki framework.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Log format string
        sqlalchemy: Enable SQLAlchemy query logging
        custom_formatter: Custom formatter (overrides default ColoredFormatter)
        custom_handlers: Custom handlers (overrides default StreamHandler)
    """
    # Use custom formatter if provided, otherwise use ColoredFormatter
    if custom_formatter:
        formatter = custom_formatter
    else:
        formatter = ColoredFormatter(format)

    # Use custom handlers if provided
    if custom_handlers:
        handlers = custom_handlers
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handlers = [handler]

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)

    # Configure Mitsuki logger
    mitsuki_logger = get_logger()
    mitsuki_logger.setLevel(getattr(logging, level.upper()))

    # Configure uvicorn loggers to use same format
    for logger_name in ["uvicorn.access", "uvicorn.error", "uvicorn"]:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        for handler in handlers:
            logger.addHandler(handler)
        logger.propagate = False

    # Configure granian loggers to use same format
    for logger_name in ["granian.access", "granian.error", "granian"]:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        for handler in handlers:
            logger.addHandler(handler)
        logger.propagate = False

    # Configure SQLAlchemy logging
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if sqlalchemy else logging.WARNING
    )


def get_granian_log_config(
    level: str = "INFO", format: str = "%(levelname)s %(message)s"
) -> Dict[str, Any]:
    """
    Get logging configuration dict for Granian.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Log format string

    Returns:
        Dictionary configuration for Granian's log_dictconfig parameter
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "colored": {
                "()": "mitsuki.core.logging.ColoredFormatter",
                "format": format,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "colored",
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {
            "granian": {
                "handlers": ["console"],
                "level": level.upper(),
                "propagate": False,
            },
            "granian.access": {
                "handlers": ["console"],
                "level": level.upper(),
                "propagate": False,
            },
            "granian.error": {
                "handlers": ["console"],
                "level": level.upper(),
                "propagate": False,
            },
        },
    }
