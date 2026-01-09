"""Weather data provider using OpenWeatherMap API."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class CurrentWeather:
    """Current weather conditions."""

    temperature: float  # Fahrenheit or Celsius based on units
    feels_like: float
    humidity: int  # Percentage
    description: str
    wind_speed: float  # mph or km/h
    wind_direction: str  # Compass direction (N, NE, etc.)


@dataclass
class DailyForecast:
    """Daily weather forecast."""

    date: str
    high_temp: float
    low_temp: float
    rain_chance: int  # Percentage


@dataclass
class AirQuality:
    """Air quality data."""

    aqi: int  # US EPA AQI (0-500)
    category: str  # Good, Moderate, Unhealthy, etc.
    pm25: float
    pm10: float
    o3: float
    no2: float
    so2: float
    co: float
    updated_at: float  # Unix timestamp


class WeatherProvider:
    """
    Provides weather and air quality data from OpenWeatherMap API.

    Data is cached and refreshed at configurable intervals.
    """

    # AQI breakpoints for US EPA scale
    AQI_BREAKPOINTS = [
        (0, 50, "Good"),
        (51, 100, "Moderate"),
        (101, 150, "Unhealthy for Sensitive"),
        (151, 200, "Unhealthy"),
        (201, 300, "Very Unhealthy"),
        (301, 500, "Hazardous"),
    ]

    def __init__(
        self,
        api_key: str,
        latitude: float,
        longitude: float,
        units: str = "imperial",
        weather_interval: int = 900,
        aqi_interval: int = 1800,
    ):
        """
        Initialize weather provider.

        Args:
            api_key: OpenWeatherMap API key
            latitude: Location latitude
            longitude: Location longitude
            units: "imperial" or "metric"
            weather_interval: Weather cache duration in seconds
            aqi_interval: AQI cache duration in seconds
        """
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.units = units
        self.weather_interval = weather_interval
        self.aqi_interval = aqi_interval

        # Cache
        self._current_weather: Optional[CurrentWeather] = None
        self._forecast: Optional[list[DailyForecast]] = None
        self._air_quality: Optional[AirQuality] = None
        self._weather_updated: float = 0
        self._aqi_updated: float = 0

    def get_current_weather(self) -> Optional[CurrentWeather]:
        """
        Get current weather conditions.

        Returns cached data if still fresh, otherwise fetches new data.
        """
        if self._is_cache_valid(self._weather_updated, self.weather_interval):
            return self._current_weather

        self._fetch_weather()
        return self._current_weather

    def get_forecast(self, days: int = 3) -> Optional[list[DailyForecast]]:
        """
        Get weather forecast.

        Args:
            days: Number of days to return (max 5)

        Returns:
            List of daily forecasts, or None if unavailable
        """
        if self._is_cache_valid(self._weather_updated, self.weather_interval):
            return self._forecast[:days] if self._forecast else None

        self._fetch_weather()
        return self._forecast[:days] if self._forecast else None

    def get_air_quality(self) -> Optional[AirQuality]:
        """Get current air quality data."""
        if self._is_cache_valid(self._aqi_updated, self.aqi_interval):
            return self._air_quality

        self._fetch_air_quality()
        return self._air_quality

    def _is_cache_valid(self, last_update: float, interval: int) -> bool:
        """Check if cached data is still valid."""
        return time.time() - last_update < interval

    def _fetch_weather(self) -> None:
        """Fetch current weather and forecast from API."""
        if not self.api_key:
            logger.warning("No API key configured, skipping weather fetch")
            return

        try:
            # Fetch current weather
            current_url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?lat={self.latitude}&lon={self.longitude}"
                f"&appid={self.api_key}&units={self.units}"
            )
            current_resp = requests.get(current_url, timeout=10)
            current_resp.raise_for_status()
            current_data = current_resp.json()

            # Parse current weather (defensive parsing)
            main = current_data.get("main", {})
            weather_list = current_data.get("weather", [{}])
            wind = current_data.get("wind", {})

            self._current_weather = CurrentWeather(
                temperature=main.get("temp", 0),
                feels_like=main.get("feels_like", 0),
                humidity=main.get("humidity", 0),
                description=(
                    weather_list[0].get("description", "Unknown").title()
                    if weather_list
                    else "Unknown"
                ),
                wind_speed=wind.get("speed", 0),
                wind_direction=self._degrees_to_compass(wind.get("deg", 0)),
            )

            # Fetch forecast
            forecast_url = (
                f"https://api.openweathermap.org/data/2.5/forecast"
                f"?lat={self.latitude}&lon={self.longitude}"
                f"&appid={self.api_key}&units={self.units}"
            )
            forecast_resp = requests.get(forecast_url, timeout=10)
            forecast_resp.raise_for_status()
            forecast_data = forecast_resp.json()

            # Parse forecast (group by day)
            self._forecast = self._parse_forecast(forecast_data)

            self._weather_updated = time.time()
            logger.debug("Weather data updated successfully")

        except requests.Timeout:
            logger.warning("Weather API request timed out")
        except requests.HTTPError as e:
            logger.warning(f"Weather API HTTP error: {e}")
        except requests.RequestException as e:
            logger.warning(f"Weather API request failed: {e}")
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to parse weather data: {e}")

    def _fetch_air_quality(self) -> None:
        """Fetch air quality data from API."""
        if not self.api_key:
            logger.warning("No API key configured, skipping AQI fetch")
            return

        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/air_pollution"
                f"?lat={self.latitude}&lon={self.longitude}"
                f"&appid={self.api_key}"
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            components = data["list"][0]["components"]

            # Calculate US EPA AQI from PM2.5 (primary pollutant)
            pm25 = components.get("pm2_5", 0)
            aqi = self._pm25_to_aqi(pm25)
            category = self._aqi_category(aqi)

            self._air_quality = AirQuality(
                aqi=aqi,
                category=category,
                pm25=components.get("pm2_5", 0),
                pm10=components.get("pm10", 0),
                o3=components.get("o3", 0),
                no2=components.get("no2", 0),
                so2=components.get("so2", 0),
                co=components.get("co", 0),
                updated_at=time.time(),
            )

            self._aqi_updated = time.time()
            logger.debug("Air quality data updated successfully")

        except requests.Timeout:
            logger.warning("AQI API request timed out")
        except requests.HTTPError as e:
            logger.warning(f"AQI API HTTP error: {e}")
        except requests.RequestException as e:
            logger.warning(f"AQI API request failed: {e}")
        except (KeyError, ValueError, IndexError) as e:
            logger.warning(f"Failed to parse AQI data: {e}")

    def _parse_forecast(self, data: dict) -> list[DailyForecast]:
        """Parse 5-day forecast into daily summaries."""
        daily: dict = {}

        for item in data.get("list", []):
            date = item["dt_txt"].split(" ")[0]
            if date not in daily:
                daily[date] = {"temps": [], "rain": []}
            daily[date]["temps"].append(item["main"]["temp"])
            daily[date]["rain"].append(int(item.get("pop", 0) * 100))

        forecasts = []
        # Explicitly sort by date to ensure chronological order
        for date, values in sorted(daily.items())[:5]:
            forecasts.append(
                DailyForecast(
                    date=date,
                    high_temp=max(values["temps"]),
                    low_temp=min(values["temps"]),
                    rain_chance=max(values["rain"]) if values["rain"] else 0,
                )
            )

        return forecasts

    @staticmethod
    def _degrees_to_compass(degrees: float) -> str:
        """Convert wind degrees to 16-point compass direction."""
        directions = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
        idx = int((degrees + 11.25) / 22.5) % 16
        return directions[idx]

    @staticmethod
    def _pm25_to_aqi(pm25: float) -> int:
        """Convert PM2.5 concentration to US EPA AQI."""
        # US EPA breakpoints for PM2.5
        breakpoints = [
            (0.0, 12.0, 0, 50),
            (12.1, 35.4, 51, 100),
            (35.5, 55.4, 101, 150),
            (55.5, 150.4, 151, 200),
            (150.5, 250.4, 201, 300),
            (250.5, 500.4, 301, 500),
        ]

        for c_low, c_high, i_low, i_high in breakpoints:
            if c_low <= pm25 <= c_high:
                aqi = ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
                return int(aqi)

        return 500 if pm25 > 500.4 else 0

    @staticmethod
    def _aqi_category(aqi: int) -> str:
        """Get AQI category name."""
        if aqi <= 50:
            return "Good"
        elif aqi <= 100:
            return "Moderate"
        elif aqi <= 150:
            return "Unhealthy for Sensitive"
        elif aqi <= 200:
            return "Unhealthy"
        elif aqi <= 300:
            return "Very Unhealthy"
        else:
            return "Hazardous"
