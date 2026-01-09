"""Configuration loading and validation for Solar Smart Clock."""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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

    def validate(self) -> list[str]:
        errors = []
        # Lazy import to avoid circular dependency
        from .views import VIEW_CLASSES

        max_view = len(VIEW_CLASSES) - 1
        if not 0 <= self.default_view <= max_view:
            errors.append(
                f"Invalid default_view {self.default_view}: must be 0-{max_view}"
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


def _dict_to_config(data: dict) -> Config:
    """Convert a dictionary to a Config object."""
    config = Config()

    if "location" in data:
        loc = data["location"]
        config.location = LocationConfig(
            name=loc.get("name", config.location.name),
            region=loc.get("region", config.location.region),
            timezone=loc.get("timezone", config.location.timezone),
            latitude=loc.get("latitude", config.location.latitude),
            longitude=loc.get("longitude", config.location.longitude),
        )

    if "display" in data:
        disp = data["display"]
        config.display = DisplayConfig(
            width=disp.get("width", config.display.width),
            height=disp.get("height", config.display.height),
            framebuffer=disp.get("framebuffer", config.display.framebuffer),
            nav_bar_height=disp.get("nav_bar_height", config.display.nav_bar_height),
        )

    if "http_server" in data:
        http = data["http_server"]
        config.http_server = HttpServerConfig(
            enabled=http.get("enabled", config.http_server.enabled),
            port=http.get("port", config.http_server.port),
            bind_address=http.get("bind_address", config.http_server.bind_address),
            rate_limit_per_second=http.get(
                "rate_limit_per_second", config.http_server.rate_limit_per_second
            ),
        )

    if "weather" in data:
        weather = data["weather"]
        config.weather = WeatherConfig(
            update_interval_seconds=weather.get(
                "update_interval_seconds", config.weather.update_interval_seconds
            ),
            units=weather.get("units", config.weather.units),
        )

    if "air_quality" in data:
        aq = data["air_quality"]
        config.air_quality = AirQualityConfig(
            update_interval_seconds=aq.get(
                "update_interval_seconds", config.air_quality.update_interval_seconds
            ),
        )

    if "touch" in data:
        touch = data["touch"]
        config.touch = TouchConfig(
            enabled=touch.get("enabled", config.touch.enabled),
            device=touch.get("device", config.touch.device),
            swipe_threshold=touch.get("swipe_threshold", config.touch.swipe_threshold),
            tap_threshold=touch.get("tap_threshold", config.touch.tap_threshold),
            tap_timeout=touch.get("tap_timeout", config.touch.tap_timeout),
        )

    if "appearance" in data:
        appearance = data["appearance"]
        config.appearance = AppearanceConfig(
            default_view=appearance.get("default_view", config.appearance.default_view),
        )

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
    key = os.environ.get("OPENWEATHER_API_KEY")
    if not key:
        logger.warning("OPENWEATHER_API_KEY environment variable not set")
    return key
