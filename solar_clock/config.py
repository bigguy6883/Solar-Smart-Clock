"""Configuration loading and validation for Solar Smart Clock."""

import dataclasses
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# Default paths to search for config
CONFIG_PATHS = [
    Path("config.json"),
    Path.home() / ".config" / "solar-clock" / "config.json",
    Path("/etc/solar-clock/config.json"),
]


@dataclass
class LocationConfig:
    """Location settings for solar calculations."""

    name: str = "Unknown"
    region: str = "Unknown"
    timezone: str = "UTC"
    latitude: float = 0.0
    longitude: float = 0.0

    def validate(self) -> list[str]:
        """Return list of validation errors, empty if valid."""
        errors = []
        if not -90 <= self.latitude <= 90:
            errors.append(f"Invalid latitude {self.latitude}: must be -90 to 90")
        if not -180 <= self.longitude <= 180:
            errors.append(f"Invalid longitude {self.longitude}: must be -180 to 180")
        if not self.timezone:
            errors.append("Timezone must not be empty")
        return errors


@dataclass
class DisplayConfig:
    """Display settings."""

    width: int = 480
    height: int = 320
    framebuffer: str = "/dev/fb1"
    nav_bar_height: int = 40

    def validate(self) -> list[str]:
        errors = []
        if self.width <= 0 or self.height <= 0:
            errors.append(f"Invalid display dimensions: {self.width}x{self.height}")
        if self.nav_bar_height < 0 or self.nav_bar_height > self.height:
            errors.append(f"Invalid nav_bar_height: {self.nav_bar_height}")
        return errors


@dataclass
class HttpServerConfig:
    """HTTP screenshot server settings."""

    enabled: bool = True
    port: int = 8080
    bind_address: str = "127.0.0.1"  # Secure default: localhost only
    rate_limit_per_second: int = 10

    def validate(self) -> list[str]:
        errors = []
        if not 1 <= self.port <= 65535:
            errors.append(f"Invalid port {self.port}: must be 1-65535")
        return errors


@dataclass
class WeatherConfig:
    """Weather API settings."""

    update_interval_seconds: int = 900  # 15 minutes
    units: str = "imperial"  # imperial or metric

    def validate(self) -> list[str]:
        errors = []
        if self.update_interval_seconds < 60:
            errors.append("Weather update interval must be at least 60 seconds")
        if self.units not in ("imperial", "metric"):
            errors.append(
                f"Invalid units '{self.units}': must be 'imperial' or 'metric'"
            )
        return errors


@dataclass
class AirQualityConfig:
    """Air quality API settings."""

    update_interval_seconds: int = 1800  # 30 minutes

    def validate(self) -> list[str]:
        errors = []
        if self.update_interval_seconds < 60:
            errors.append("Air quality update interval must be at least 60 seconds")
        return errors


@dataclass
class TouchConfig:
    """Touchscreen settings."""

    enabled: bool = True
    device: str = "/dev/input/event0"
    swipe_threshold: int = 80
    tap_threshold: int = 30
    tap_timeout: float = 0.4

    def validate(self) -> list[str]:
        errors = []
        if self.swipe_threshold <= 0:
            errors.append("Swipe threshold must be positive")
        if self.tap_threshold <= 0:
            errors.append("Tap threshold must be positive")
        if self.tap_timeout <= 0:
            errors.append("Tap timeout must be positive")
        return errors


@dataclass
class AppearanceConfig:
    """Appearance settings."""

    default_view: int = 0
    theme_mode: Literal["auto", "day", "night"] = "auto"

    def validate(self) -> list[str]:
        errors = []
        # Lazy import to avoid circular dependency
        from .views import VIEW_CLASSES

        max_view = len(VIEW_CLASSES) - 1
        if not 0 <= self.default_view <= max_view:
            errors.append(
                f"Invalid default_view {self.default_view}: must be 0-{max_view}"
            )
        if self.theme_mode not in ("auto", "day", "night"):
            errors.append(
                f"Invalid theme_mode '{self.theme_mode}': must be 'auto', 'day', or 'night'"
            )
        return errors


@dataclass
class Config:
    """Main configuration container."""

    location: LocationConfig = field(default_factory=LocationConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    http_server: HttpServerConfig = field(default_factory=HttpServerConfig)
    weather: WeatherConfig = field(default_factory=WeatherConfig)
    air_quality: AirQualityConfig = field(default_factory=AirQualityConfig)
    touch: TouchConfig = field(default_factory=TouchConfig)
    appearance: AppearanceConfig = field(default_factory=AppearanceConfig)

    def validate(self) -> list[str]:
        """Validate all configuration sections. Returns list of errors."""
        errors = []
        errors.extend(self.location.validate())
        errors.extend(self.display.validate())
        errors.extend(self.http_server.validate())
        errors.extend(self.weather.validate())
        errors.extend(self.air_quality.validate())
        errors.extend(self.touch.validate())
        errors.extend(self.appearance.validate())
        return errors


def _dataclass_from_dict(cls, data: dict):
    """Create a dataclass instance from a dict, using field defaults for missing keys."""
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name in data:
            kwargs[f.name] = data[f.name]
        elif f.default is not dataclasses.MISSING:
            kwargs[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:
            kwargs[f.name] = f.default_factory()
        # If no default, let cls(**kwargs) raise naturally
    return cls(**kwargs)


# Mapping from config JSON keys to their dataclass types
_CONFIG_SECTIONS = {
    "location": ("location", LocationConfig),
    "display": ("display", DisplayConfig),
    "http_server": ("http_server", HttpServerConfig),
    "weather": ("weather", WeatherConfig),
    "air_quality": ("air_quality", AirQualityConfig),
    "touch": ("touch", TouchConfig),
    "appearance": ("appearance", AppearanceConfig),
}


def _dict_to_config(data: dict) -> Config:
    """Convert a dictionary to a Config object."""
    config = Config()
    for key, (attr, cls) in _CONFIG_SECTIONS.items():
        if key in data:
            setattr(config, attr, _dataclass_from_dict(cls, data[key]))
    return config


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from JSON file.

    Args:
        config_path: Explicit path to config file. If None, searches default paths.

    Returns:
        Config object with loaded settings.

    Raises:
        FileNotFoundError: If no config file found and config_path was explicit.
        ValueError: If config file has validation errors.
    """
    # Determine which path to use
    if config_path is not None:
        paths_to_try = [config_path]
    else:
        paths_to_try = CONFIG_PATHS

    # Find first existing config file
    found_path = None
    for path in paths_to_try:
        if path.exists():
            found_path = path
            break

    if found_path is None:
        if config_path is not None:
            raise FileNotFoundError(f"Config file not found: {config_path}")
        logger.warning("No config file found, using defaults")
        return Config()

    # Load and parse JSON
    logger.info(f"Loading config from {found_path}")
    try:
        with open(found_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file {found_path}: {e}")

    # Convert to Config object
    config = _dict_to_config(data)

    # Validate
    errors = config.validate()
    if errors:
        error_msg = "Config validation errors:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        raise ValueError(error_msg)

    return config


def get_api_key() -> Optional[str]:
    """
    Get OpenWeatherMap API key from environment.

    Returns:
        API key string, or None if not set.
    """
    return os.environ.get("OPENWEATHER_API_KEY") or None
