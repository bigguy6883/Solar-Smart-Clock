"""Tests for weather data provider."""

import pytest
from unittest.mock import patch, MagicMock
import requests

from solar_clock.data.weather import WeatherProvider, CurrentWeather


class TestWeatherProvider:
    """Tests for WeatherProvider."""

    @pytest.fixture
    def provider(self):
        """Create a weather provider instance."""
        return WeatherProvider(
            api_key="test_api_key",
            latitude=40.7128,
            longitude=-74.0060,
            units="imperial",
            weather_interval=900,
            aqi_interval=1800,
        )

    def test_init(self, provider):
        """Test provider initialization."""
        assert provider.api_key == "test_api_key"
        assert provider.latitude == 40.7128
        assert provider.longitude == -74.0060
        assert provider.units == "imperial"

    def test_get_current_weather_success(
        self, provider, mock_weather_response, mock_forecast_response
    ):
        """Test successful weather fetch."""
        with patch("solar_clock.data.weather.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.side_effect = [mock_weather_response, mock_forecast_response]
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            weather = provider.get_current_weather()

            assert weather is not None
            assert weather.temperature == 72.5
            assert weather.humidity == 65
            assert "cloudy" in weather.description.lower()

    def test_get_current_weather_cached(self, provider):
        """Test weather data is cached."""
        provider._current_weather = CurrentWeather(
            temperature=70.0,
            feels_like=68.0,
            humidity=50,
            description="Cached",
            wind_speed=3.0,
            wind_direction="N",
        )
        provider._weather_updated = 9999999999  # Far future

        weather = provider.get_current_weather()

        assert weather.description == "Cached"

    def test_get_current_weather_timeout(self, provider):
        """Test timeout handling."""
        with patch("solar_clock.data.weather.requests.get") as mock_get:
            mock_get.side_effect = requests.Timeout()

            # Should not raise, just return None
            weather = provider.get_current_weather()
            assert weather is None

    def test_get_current_weather_http_error(self, provider):
        """Test HTTP error handling."""
        with patch("solar_clock.data.weather.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
            mock_get.return_value = mock_resp

            weather = provider.get_current_weather()
            assert weather is None

    def test_get_forecast(
        self, provider, mock_weather_response, mock_forecast_response
    ):
        """Test forecast retrieval."""
        with patch("solar_clock.data.weather.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.side_effect = [mock_weather_response, mock_forecast_response]
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            forecast = provider.get_forecast(3)

            assert forecast is not None
            assert len(forecast) <= 3

    def test_get_air_quality_success(self, provider, mock_aqi_response):
        """Test successful AQI fetch."""
        with patch("solar_clock.data.weather.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_aqi_response
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            aqi = provider.get_air_quality()

            assert aqi is not None
            assert aqi.pm25 == 12.5
            assert aqi.aqi > 0
            assert aqi.category in [
                "Good",
                "Moderate",
                "Unhealthy for Sensitive",
                "Unhealthy",
                "Very Unhealthy",
                "Hazardous",
            ]

    def test_degrees_to_compass(self):
        """Test wind direction conversion."""
        assert WeatherProvider._degrees_to_compass(0) == "N"
        assert WeatherProvider._degrees_to_compass(90) == "E"
        assert WeatherProvider._degrees_to_compass(180) == "S"
        assert WeatherProvider._degrees_to_compass(270) == "W"
        assert WeatherProvider._degrees_to_compass(45) == "NE"
        assert WeatherProvider._degrees_to_compass(315) == "NW"

    def test_pm25_to_aqi_good(self):
        """Test PM2.5 to AQI conversion - good range."""
        aqi = WeatherProvider._pm25_to_aqi(5.0)
        assert 0 <= aqi <= 50

    def test_pm25_to_aqi_moderate(self):
        """Test PM2.5 to AQI conversion - moderate range."""
        aqi = WeatherProvider._pm25_to_aqi(20.0)
        assert 51 <= aqi <= 100

    def test_pm25_to_aqi_unhealthy(self):
        """Test PM2.5 to AQI conversion - unhealthy range."""
        aqi = WeatherProvider._pm25_to_aqi(100.0)
        assert aqi > 100

    def test_aqi_category(self):
        """Test AQI category assignment."""
        assert WeatherProvider._aqi_category(25) == "Good"
        assert WeatherProvider._aqi_category(75) == "Moderate"
        assert WeatherProvider._aqi_category(125) == "Unhealthy for Sensitive"
        assert WeatherProvider._aqi_category(175) == "Unhealthy"
        assert WeatherProvider._aqi_category(250) == "Very Unhealthy"
        assert WeatherProvider._aqi_category(350) == "Hazardous"

    def test_no_api_key(self):
        """Test behavior without API key."""
        provider = WeatherProvider(
            api_key="",
            latitude=40.0,
            longitude=-74.0,
        )
        weather = provider.get_current_weather()
        assert weather is None

    def test_parse_forecast_skips_malformed_entries(self, provider):
        """A forecast entry missing 'main' must not abort the entire parse."""
        data = {
            "list": [
                {"dt_txt": "2026-02-20 12:00:00", "main": {"temp": 72.0}, "pop": 0.1},
                {"dt_txt": "2026-02-20 15:00:00", "pop": 0.2},  # missing 'main'
                {"dt_txt": "2026-02-21 12:00:00", "main": {"temp": 65.0}, "pop": 0.3},
            ]
        }
        result = provider._parse_forecast(data)
        dates = [f.date for f in result]
        assert "2026-02-20" in dates, "First day dropped due to malformed entry"
        assert "2026-02-21" in dates, "Second day dropped due to malformed entry"

    def test_parse_forecast_skips_all_malformed_day(self, provider):
        """When ALL entries for a date are malformed, that date is skipped but others are kept."""
        data = {
            "list": [
                # All entries for 2026-02-20 missing 'main'
                {"dt_txt": "2026-02-20 09:00:00", "pop": 0.1},
                {"dt_txt": "2026-02-20 12:00:00", "pop": 0.2},
                # 2026-02-21 is fine
                {"dt_txt": "2026-02-21 12:00:00", "main": {"temp": 65.0}, "pop": 0.3},
            ]
        }
        result = provider._parse_forecast(data)
        dates = [f.date for f in result]
        assert "2026-02-20" not in dates, "Fully-malformed date should be skipped"
        assert "2026-02-21" in dates, "Valid date should still appear"

    def test_weather_fetch_atomic_on_forecast_failure(self, provider):
        """If forecast fails, neither _current_weather nor _weather_updated should change."""
        old_weather = provider._current_weather  # None initially
        old_updated = provider._weather_updated  # 0.0 initially

        good_resp = MagicMock()
        good_resp.raise_for_status.return_value = None
        good_resp.json.return_value = {
            "main": {"temp": 72, "feels_like": 70, "humidity": 50},
            "weather": [{"description": "clear sky"}],
            "wind": {"speed": 5, "deg": 180},
        }
        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = requests.HTTPError("429")

        def fake_get(url, timeout=10):
            if "forecast" in url:
                return bad_resp
            return good_resp

        with patch("solar_clock.data.weather.requests.get", side_effect=fake_get):
            provider._fetch_weather()

        assert (
            provider._current_weather is old_weather
        ), "_current_weather was updated despite forecast failure"
        assert (
            provider._weather_updated == old_updated
        ), "_weather_updated timestamp advanced despite partial failure"
