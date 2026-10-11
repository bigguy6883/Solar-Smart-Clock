"""Tests for the web page's data service (GET /api/now)."""

import dataclasses
import datetime
import json
import logging
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from solar_clock.data.weather import AirQuality, CurrentWeather, DailyForecast
from solar_clock.views.theme import Theme, ThemeManager
from solar_clock.web_api import WebDataService, hex_color, iso

TOP_LEVEL = {
    "generated_at",
    "location",
    "units",
    "theme",
    "sun",
    "weather",
    "air_quality",
    "moon",
}


@pytest.fixture
def weather():
    """A shared WeatherProvider stand-in that returns the real dataclasses."""
    provider = MagicMock()
    provider.get_current_weather.return_value = CurrentWeather(
        temperature=64.5,
        feels_like=63.2,
        humidity=58,
        description="Scattered Clouds",
        wind_speed=7.4,
        wind_direction="WSW",
    )
    provider.get_forecast.return_value = [
        DailyForecast(date="2026-10-08", high_temp=66.1, low_temp=51.3, rain_chance=10)
    ]
    provider.get_air_quality.return_value = AirQuality(
        aqi=42,
        category="Good",
        pm25=10.1,
        pm10=18.4,
        o3=61.2,
        no2=12.7,
        so2=1.9,
        co=230.5,
        updated_at=1791485880.0,  # 2026-10-08 18:58 UTC = 2:58 PM in New York
    )
    return provider


@pytest.fixture
def service(sample_config, weather):
    return WebDataService(sample_config, weather=weather, theme_mode=lambda: "auto")


def test_build_now_is_json_with_every_section(service):
    data = json.loads(json.dumps(service.build_now()))
    assert set(data) == TOP_LEVEL
    assert data["location"] == {"name": "Test City", "timezone": "America/New_York"}
    assert data["units"] == "imperial"
    for section in ("theme", "sun", "weather", "air_quality", "moon"):
        assert data[section] is not None, section


def test_times_carry_the_configured_timezone(service):
    tz = ZoneInfo("America/New_York")
    data = service.build_now()
    generated = datetime.datetime.fromisoformat(data["generated_at"])
    assert generated.utcoffset() == tz.utcoffset(generated.replace(tzinfo=None))
    sunrise = datetime.datetime.fromisoformat(data["sun"]["times"]["sunrise"])
    assert sunrise.utcoffset() == tz.utcoffset(sunrise.replace(tzinfo=None))
    updated = datetime.datetime.fromisoformat(data["air_quality"]["updated_at"])
    assert data["air_quality"]["updated_at"] == "2026-10-08T14:58:00-04:00"
    assert updated.utcoffset() == datetime.timedelta(hours=-4)


def test_weather_sections_pass_values_through(service):
    data = service.build_now()
    assert data["weather"]["current"]["temperature"] == 64.5
    assert data["weather"]["current"]["description"] == "Scattered Clouds"
    assert data["weather"]["forecast"][0]["rain_chance"] == 10
    assert data["air_quality"]["aqi"] == 42
    assert data["air_quality"]["co"] == 230.5


def test_weather_and_air_quality_are_null_without_a_provider(sample_config):
    service = WebDataService(sample_config, weather=None, theme_mode=lambda: "auto")
    data = service.build_now()
    assert data["weather"] is None
    assert data["air_quality"] is None
    assert data["sun"] is not None


def test_weather_is_null_when_there_is_no_current_reading(service, weather):
    weather.get_current_weather.return_value = None
    weather.get_air_quality.return_value = None
    data = service.build_now()
    assert data["weather"] is None
    assert data["air_quality"] is None


def test_a_failing_section_is_null_and_logged(service, caplog):
    service._solar.get_sun_times = MagicMock(side_effect=RuntimeError("astral broke"))
    with caplog.at_level(logging.ERROR, logger="solar_clock.web_api"):
        data = service.build_now()
    assert data["sun"] is None
    assert data["moon"] is not None
    assert data["weather"] is not None
    assert "'sun' failed" in caplog.text


def test_moon_is_null_when_ephem_is_unavailable(service):
    service._lunar = MagicMock(available=False)
    assert service.build_now()["moon"] is None


def test_palettes_cover_every_theme_colour(service):
    theme = service.build_now()["theme"]
    fields = {f.name for f in dataclasses.fields(Theme)} - {"name"}
    assert set(theme["palettes"]["day"]) == fields
    assert set(theme["palettes"]["night"]) == fields
    assert theme["palettes"]["night"]["background"] == "#000000"
    assert theme["palettes"]["day"]["accent_sun"] == "#a06400"


def test_named_colours_include_the_header_colours(service):
    named = service.build_now()["theme"]["colors"]
    assert named["LIGHT_BLUE"] == "#87ceeb"
    assert named["ORANGE"] == "#ff8c00"
    assert named["PURPLE"] == "#9370db"
    assert named["DARK_BLUE"] == "#191970"


@pytest.mark.parametrize("mode", ["day", "night"])
def test_follows_the_clock_theme_mode_without_touching_it(sample_config, weather, mode):
    service = WebDataService(sample_config, weather=weather, theme_mode=lambda: mode)
    theme = service.build_now()["theme"]
    assert theme["mode"] == mode
    assert theme["active"] == mode
    # The clock's singleton ThemeManager is never created or changed.
    assert ThemeManager.get_instance() is None


def test_hex_color():
    assert hex_color((255, 140, 0)) == "#ff8c00"


def test_iso_refuses_naive_datetimes():
    with pytest.raises(ValueError):
        naive = datetime.datetime(2026, 10, 8, 12, 0)  # noqa: DTZ001 - on purpose
        iso(naive, ZoneInfo("UTC"))
    assert iso(None, ZoneInfo("UTC")) is None
