import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from colorama import Fore, Style

from mitsuki.core.logging import get_logger
from mitsuki.core.utils import get_active_profile

logger = get_logger()

# Boolean value constants
TRUTHY_VALUES = ("true", "yes", "on", "1")
FALSY_VALUES = ("false", "no", "off", "0")


class ConfigurationProperties:
    """
    Manages application configuration from multiple sources.
    Priority (highest to lowest):
    1. application-{profile}.yml - Profile-specific configuration
    2. application.yml - Application configuration
    3. Environment variables (MITSUKI_*) - Fallback/container overrides
    4. Default configuration - Framework defaults
    """

    def __init__(self, profile: Optional[str] = None):
        self.profile = profile or get_active_profile()
        self._properties: Dict[str, Any] = {}
        self._sources: Dict[str, str] = {}  # Track source of each config key
        self._load_configuration()

    def _load_configuration(self):
        """Load configuration from files"""
        # Load mitsuki defaults first
        defaults_path = Path(__file__).parent / "defaults.yml"
        if defaults_path.exists():
            self._load_yaml(defaults_path, source="default configuration")

        # TODO: Formalize the file location and structure.
        config_paths = [
            Path("application.yml"),
            Path("application.yaml"),
            Path("config/application.yml"),
            Path("config/application.yaml"),
        ]

        # Load base configuration
        for config_path in config_paths:
            if config_path.exists():
                logger.info(f"Loading configuration from {config_path}")
                self._load_yaml(config_path, source=str(config_path))
                break

        # Load profile-specific configuration (overrides base)
        if self.profile != "default":
            profile_paths = [
                Path(f"application-{self.profile}.yml"),
                Path(f"application-{self.profile}.yaml"),
                Path(f"config/application-{self.profile}.yml"),
                Path(f"config/application-{self.profile}.yaml"),
            ]
            for profile_path in profile_paths:
                if profile_path.exists():
                    logger.info(f"Loading profile configuration from {profile_path}")
                    self._load_yaml(profile_path, source=str(profile_path))
                    break

    def _load_yaml(self, path: Path, source: str = ""):
        """Load YAML configuration file"""
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
                if data:
                    self._flatten_dict(data, self._properties, source=source)
        except Exception as e:
            logger.warning(f"Failed to load configuration from {path}: {e}")

    def load_from_file(self, path):
        """Load configuration from a specific file (for testing/manual loading)"""
        file_path = Path(path) if not isinstance(path, Path) else path
        self._load_yaml(file_path)

    def _flatten_dict(
        self, data: Dict, target: Dict, prefix: str = "", source: str = ""
    ):
        """
        Flatten nested dictionary into dot-notation keys.
        Example: {"server": {"port": 8000}} -> {"server.port": 8000}
        """
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                self._flatten_dict(value, target, full_key, source=source)
            else:
                target[full_key] = value
                if source:
                    self._sources[full_key] = source

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Priority (highest to lowest):
        1. Loaded properties (application-{profile}.yml, application.yml)
        2. Environment variables (MITSUKI_*)
        3. Default value

        Args:
            key: Configuration key in dot notation
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        # Check loaded properties first (application.yml, profile configs)
        if key in self._properties:
            return self._properties[key]

        # Fall back to environment variable
        env_key = f"MITSUKI_{key.upper().replace('.', '_')}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            # Track environment variable source
            self._sources[key] = f"environment variable ({env_key})"
            return self._parse_value(env_value)

        # Finally use default
        return default

    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type (for env vars)"""
        lower_val = value.lower()

        # Boolean
        if lower_val in TRUTHY_VALUES:
            return True
        if lower_val in FALSY_VALUES:
            return False

        try:
            parsed = float(value)
            return int(parsed) if parsed.is_integer() else parsed
        except ValueError:
            return value

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value"""
        value = self.get(key, default)
        return int(value) if value is not None else default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in TRUTHY_VALUES
        return bool(value)

    def get_str(self, key: str, default: str = "") -> str:
        """Get string configuration value"""
        value = self.get(key, default)
        return str(value) if value is not None else default

    def __getitem__(self, key: str) -> Any:
        """Support dict-like access"""
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator"""
        return (
            key in self._properties
            or f"MITSUKI_{key.upper().replace('.', '_')}" in os.environ
        )

    def get_config_sources(self) -> Dict[str, str]:
        """
        Get all configuration keys and their sources.

        Returns:
            Dictionary mapping config keys to their source descriptions
        """
        return dict(sorted(self._sources.items()))


_config: Optional[ConfigurationProperties] = None


def get_config(profile: Optional[str] = None) -> ConfigurationProperties:
    global _config
    if _config is None:
        _config = ConfigurationProperties(profile=profile)
    return _config


def reload_config(profile: Optional[str] = None):
    global _config
    _config = ConfigurationProperties(profile=profile)
    return _config


def log_config_sources(config, logger, max_cols=2, padding=1):
    sources = config.get_config_sources()
    grouped = defaultdict(list)

    for key, source in sources.items():
        grouped[source].append(key)

    logger.info("")
    logger.info(Fore.BLUE + "Configuration sources:" + Style.RESET_ALL)
    logger.info("")

    def color_for_source(src):
        s = src.lower()
        if "default" in s:
            return Fore.GREEN
        if "application" in s:
            return Fore.YELLOW
        if "env" in s:
            return Fore.MAGENTA
        return Fore.CYAN

    for source, keys in grouped.items():
        logger.info(color_for_source(source) + f"[{source}]" + Style.RESET_ALL)

        col_width = max(len(k) for k in keys) + padding
        cols = max_cols
        rows = [keys[i : i + cols] for i in range(0, len(keys), cols)]

        table_width = col_width * cols
        top = "┌" + "─" * table_width + "┐"
        bottom = "└" + "─" * table_width + "┘"

        logger.info(top)
        for row in rows:
            line = "│"
            for col in row:
                line += col.ljust(col_width)
            # empty cells
            if len(row) < cols:
                line += " " * (col_width * (cols - len(row)))
            line += "│"
            logger.info(line)
        logger.info(bottom)
        logger.info("")
