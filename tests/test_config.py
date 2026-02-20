"""Tests for configuration loading and validation."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from solar_clock.config import (
    Config,
    LocationConfig,
    DisplayConfig,
    HttpServerConfig,
    WeatherConfig,
    load_config,
    get_api_key,
    _dict_to_config,
)


class TestLocationConfig:
    """Tests for LocationConfig validation."""

    def test_valid_location(self):
        """Test valid location config."""
        loc = LocationConfig(
            name="New York",
            region="NY, USA",
            timezone="America/New_York",
            latitude=40.7128,
            longitude=-74.0060,
        )
        errors = loc.validate()
        assert errors == []

    def test_invalid_latitude_too_high(self):
        """Test latitude over 90 is invalid."""
        loc = LocationConfig(latitude=91.0, longitude=0.0)
        errors = loc.validate()
        assert any("latitude" in e.lower() for e in errors)

    def test_invalid_latitude_too_low(self):
        """Test latitude under -90 is invalid."""
        loc = LocationConfig(latitude=-91.0, longitude=0.0)
        errors = loc.validate()
        assert any("latitude" in e.lower() for e in errors)

    def test_invalid_longitude_too_high(self):
        """Test longitude over 180 is invalid."""
        loc = LocationConfig(latitude=0.0, longitude=181.0)
        errors = loc.validate()
        assert any("longitude" in e.lower() for e in errors)

    def test_invalid_longitude_too_low(self):
        """Test longitude under -180 is invalid."""
        loc = LocationConfig(latitude=0.0, longitude=-181.0)
        errors = loc.validate()
        assert any("longitude" in e.lower() for e in errors)

    def test_empty_timezone(self):
        """Test empty timezone is invalid."""
        loc = LocationConfig(timezone="")
        errors = loc.validate()
        assert any("timezone" in e.lower() for e in errors)


class TestDisplayConfig:
    """Tests for DisplayConfig validation."""

    def test_valid_display(self):
        """Test valid display config."""
        disp = DisplayConfig(width=480, height=320, nav_bar_height=40)
        errors = disp.validate()
        assert errors == []

    def test_invalid_width(self):
        """Test zero width is invalid."""
        disp = DisplayConfig(width=0, height=320)
        errors = disp.validate()
        assert any("dimensions" in e.lower() for e in errors)

    def test_invalid_nav_bar_too_large(self):
        """Test nav bar larger than height is invalid."""
        disp = DisplayConfig(width=480, height=320, nav_bar_height=400)
        errors = disp.validate()
        assert any("nav_bar" in e.lower() for e in errors)


class TestHttpServerConfig:
    """Tests for HttpServerConfig validation."""

    def test_valid_server(self):
        """Test valid server config."""
        http = HttpServerConfig(port=8080, bind_address="127.0.0.1")
        errors = http.validate()
        assert errors == []

    def test_invalid_port_zero(self):
        """Test port 0 is invalid."""
        http = HttpServerConfig(port=0)
        errors = http.validate()
        assert any("port" in e.lower() for e in errors)

    def test_invalid_port_too_high(self):
        """Test port over 65535 is invalid."""
        http = HttpServerConfig(port=70000)
        errors = http.validate()
        assert any("port" in e.lower() for e in errors)

    def test_default_bind_localhost(self):
        """Test default bind address is localhost."""
        http = HttpServerConfig()
        assert http.bind_address == "127.0.0.1"


class TestWeatherConfig:
    """Tests for WeatherConfig validation."""

    def test_valid_weather(self):
        """Test valid weather config."""
        weather = WeatherConfig(update_interval_seconds=900, units="imperial")
        errors = weather.validate()
        assert errors == []

    def test_invalid_interval_too_short(self):
        """Test interval under 60s is invalid."""
        weather = WeatherConfig(update_interval_seconds=30)
        errors = weather.validate()
        assert any("interval" in e.lower() for e in errors)

    def test_invalid_units(self):
        """Test invalid units value."""
        weather = WeatherConfig(units="kelvin")
        errors = weather.validate()
        assert any("units" in e.lower() for e in errors)


class TestConfigLoading:
    """Tests for config file loading."""

    def test_load_from_file(self, temp_config_file):
        """Test loading config from file."""
        config = load_config(temp_config_file)
        assert config.location.name == "Test City"
        assert config.location.latitude == 40.7128
        assert config.display.width == 480

    def test_load_missing_file_explicit(self, tmp_path):
        """Test loading non-existent explicit file raises error."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.json")

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises error."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")
        with pytest.raises(ValueError) as exc_info:
            load_config(bad_file)
        assert "Invalid JSON" in str(exc_info.value)

    def test_load_validation_error(self, tmp_path):
        """Test loading config with validation errors raises error."""
        bad_config = tmp_path / "bad_config.json"
        with open(bad_config, "w") as f:
            json.dump({"location": {"latitude": 999}}, f)
        with pytest.raises(ValueError) as exc_info:
            load_config(bad_config)
        assert "validation" in str(exc_info.value).lower()

    def test_load_defaults_when_no_file(self):
        """Test defaults used when no config file found."""
        with patch(
            "solar_clock.config.CONFIG_PATHS", [Path("/nonexistent/config.json")]
        ):
            config = load_config(None)
            assert isinstance(config, Config)
            assert config.display.width == 480  # Default

    def test_dict_to_config_partial(self):
        """Test converting partial dict uses defaults."""
        config = _dict_to_config({"location": {"name": "Custom"}})
        assert config.location.name == "Custom"
        assert config.location.latitude == 0.0  # Default
        assert config.display.width == 480  # Default


def test_dataclass_from_dict_does_not_call_constructor_for_defaults():
    """_dataclass_from_dict must not instantiate cls() just to read defaults."""
    from unittest.mock import patch
    from solar_clock.config import _dataclass_from_dict, WeatherConfig

    constructor_calls = []
    real_init = WeatherConfig.__init__

    def tracking_init(self, *args, **kwargs):
        constructor_calls.append(1)
        return real_init(self, *args, **kwargs)

    with patch.object(WeatherConfig, "__init__", tracking_init):
        result = _dataclass_from_dict(WeatherConfig, {"units": "metric"})

    # Should be called exactly once (for the final cls(**kwargs)), not twice
    assert (
        len(constructor_calls) == 1
    ), f"Expected 1 constructor call, got {len(constructor_calls)}"
    assert result.units == "metric"


class TestGetApiKey:
    """Tests for API key retrieval."""

    def test_get_api_key_from_env(self):
        """Test getting API key from environment."""
        with patch.dict(os.environ, {"OPENWEATHER_API_KEY": "test_key_123"}):
            key = get_api_key()
            assert key == "test_key_123"

    def test_get_api_key_missing(self):
        """Test None returned when API key not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop("OPENWEATHER_API_KEY", None)
            key = get_api_key()
            assert key is None
