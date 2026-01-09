"""Pytest fixtures for Solar Smart Clock tests."""

import datetime
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from solar_clock.views.base import DataProviders  # noqa: E402


@pytest.fixture
def sample_config_dict():
    """Sample configuration dictionary."""
    return {
        "location": {
            "name": "Test City",
            "region": "Test Region",
            "timezone": "America/New_York",
            "latitude": 40.7128,
            "longitude": -74.0060,
        },
        "display": {
            "width": 480,
            "height": 320,
            "framebuffer": "/dev/fb1",
            "nav_bar_height": 40,
        },
        "http_server": {"enabled": True, "port": 8080, "bind_address": "127.0.0.1"},
        "weather": {"update_interval_seconds": 900, "units": "imperial"},
        "air_quality": {"update_interval_seconds": 1800},
        "touch": {
            "enabled": True,
            "device": "/dev/input/event0",
            "swipe_threshold": 80,
            "tap_threshold": 30,
            "tap_timeout": 0.4,
        },
        "appearance": {"default_view": 0},
    }


@pytest.fixture
def temp_config_file(tmp_path, sample_config_dict):
    """Create a temporary config file."""
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(sample_config_dict, f)
    return config_path


@pytest.fixture
def sample_config(sample_config_dict):
    """Create a Config object from sample data."""
    from solar_clock.config import _dict_to_config

    return _dict_to_config(sample_config_dict)


@pytest.fixture
def mock_weather_response():
    """Mock OpenWeatherMap current weather response."""
    return {
        "main": {"temp": 72.5, "feels_like": 70.0, "humidity": 65},
        "weather": [{"description": "partly cloudy", "main": "Clouds"}],
        "wind": {"speed": 5.5, "deg": 180},
    }


@pytest.fixture
def mock_forecast_response():
    """Mock OpenWeatherMap forecast response."""
    return {
        "list": [
            {
                "dt_txt": "2024-01-15 12:00:00",
                "main": {"temp": 75},
                "pop": 0.2,
                "weather": [{"description": "sunny"}],
            },
            {
                "dt_txt": "2024-01-15 18:00:00",
                "main": {"temp": 70},
                "pop": 0.1,
                "weather": [{"description": "clear"}],
            },
            {
                "dt_txt": "2024-01-16 12:00:00",
                "main": {"temp": 68},
                "pop": 0.5,
                "weather": [{"description": "rain"}],
            },
        ]
    }


@pytest.fixture
def mock_aqi_response():
    """Mock OpenWeatherMap air quality response."""
    return {
        "list": [
            {
                "components": {
                    "pm2_5": 12.5,
                    "pm10": 25.0,
                    "o3": 45.0,
                    "no2": 15.0,
                    "so2": 5.0,
                    "co": 200.0,
                }
            }
        ]
    }


@pytest.fixture
def mock_providers():
    """Create mock data providers."""
    weather = MagicMock()
    weather.get_current_weather.return_value = MagicMock(
        temperature=72.5,
        feels_like=70.0,
        humidity=65,
        description="Partly Cloudy",
        wind_speed=5.5,
        wind_direction="S",
    )

    solar = MagicMock()
    solar.get_sun_times.return_value = MagicMock(
        dawn=datetime.datetime(2024, 1, 15, 6, 30),
        sunrise=datetime.datetime(2024, 1, 15, 7, 0),
        noon=datetime.datetime(2024, 1, 15, 12, 30),
        sunset=datetime.datetime(2024, 1, 15, 17, 30),
        dusk=datetime.datetime(2024, 1, 15, 18, 0),
    )
    solar.get_day_length.return_value = 10.5
    solar.get_day_length_change.return_value = 1.5
    solar.get_solar_position.return_value = MagicMock(elevation=35.5, azimuth=180.0)
    solar.get_golden_hour.return_value = (
        MagicMock(
            start=datetime.datetime(2024, 1, 15, 6, 30),
            end=datetime.datetime(2024, 1, 15, 7, 30),
        ),
        MagicMock(
            start=datetime.datetime(2024, 1, 15, 17, 0),
            end=datetime.datetime(2024, 1, 15, 18, 0),
        ),
    )
    # Return a proper tuple for next_solar_event
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/New_York")
    future_time = datetime.datetime.now(tz) + datetime.timedelta(hours=2)
    solar.get_next_solar_event.return_value = ("Sunset", future_time)

    lunar = MagicMock()
    lunar.available = True
    lunar.get_moon_phase.return_value = MagicMock(
        phase=0.25,
        illumination=50.0,
        phase_name="First Quarter",
        next_new=datetime.date(2024, 1, 20),
        next_full=datetime.date(2024, 1, 28),
        days_to_new=5,
        days_to_full=13,
    )
    lunar.get_solstice_equinox.return_value = MagicMock(
        spring_equinox=datetime.date(2024, 3, 20),
        summer_solstice=datetime.date(2024, 6, 21),
        fall_equinox=datetime.date(2024, 9, 22),
        winter_solstice=datetime.date(2024, 12, 21),
    )
    lunar.get_analemma_data.return_value = []
    lunar.get_equation_of_time.return_value = 5.2  # Minutes

    return DataProviders(weather=weather, solar=solar, lunar=lunar)
