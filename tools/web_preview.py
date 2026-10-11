"""Serve the Solar Clock web page on homelab, without a display.

Runs only the HTTP server and the page's data service, so the page can be
built and checked from a phone before anything is deployed to clock.local.
The TFT endpoints (/screenshot, /next, ...) answer 503 here: there is no clock.

    ./venv/bin/python -m tools.web_preview --config config.example.json --port 8091

Weather needs OPENWEATHER_API_KEY in the environment; without it, pass
--sample-weather to fill the weather views with fixed example data.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from solar_clock.config import get_api_key, load_config
from solar_clock.data import WeatherProvider
from solar_clock.data.weather import (
    AirQuality,
    CurrentWeather,
    DailyForecast,
)
from solar_clock.http_server import create_server
from solar_clock.web_api import WebDataService
from solar_clock.web_static import StaticSite


class SampleWeather(WeatherProvider):
    """Fixed example weather, so the views can be checked without an API key."""

    def __init__(self) -> None:
        super().__init__(api_key="", latitude=0.0, longitude=0.0)

    def get_current_weather(self) -> CurrentWeather | None:
        return CurrentWeather(
            temperature=64.5,
            feels_like=63.2,
            humidity=58,
            description="Scattered Clouds",
            wind_speed=7.4,
            wind_direction="WSW",
        )

    def get_forecast(self, days: int = 3) -> list[DailyForecast] | None:
        today = time.strftime("%Y-%m-%d")
        return [
            DailyForecast(date=today, high_temp=66.1, low_temp=51.3, rain_chance=10),
            DailyForecast(date=today, high_temp=61.0, low_temp=48.8, rain_chance=40),
            DailyForecast(date=today, high_temp=58.4, low_temp=45.0, rain_chance=0),
        ][:days]

    def get_air_quality(self) -> AirQuality | None:
        return AirQuality(
            aqi=42,
            category="Good",
            pm25=10.1,
            pm10=18.4,
            o3=61.2,
            no2=12.7,
            so2=1.9,
            co=230.5,
            updated_at=time.time(),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Serve the web page without a display."
    )
    parser.add_argument("--config", type=Path, required=True, help="config.json to use")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--bind", default="0.0.0.0", help="address to listen on")
    parser.add_argument(
        "--theme", choices=["auto", "day", "night"], help="override the theme mode"
    )
    parser.add_argument(
        "--sample-weather", action="store_true", help="use fixed example weather"
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    config = load_config(args.config)
    config.http_server.enabled = True
    config.http_server.port = args.port
    config.http_server.bind_address = args.bind

    api_key = get_api_key()
    weather: WeatherProvider | None = None
    if args.sample_weather:
        weather = SampleWeather()
    elif api_key:
        weather = WeatherProvider(
            api_key=api_key,
            latitude=config.location.latitude,
            longitude=config.location.longitude,
            units=config.weather.units,
            weather_interval=config.weather.update_interval_seconds,
            aqi_interval=config.air_quality.update_interval_seconds,
        )

    mode = args.theme or config.appearance.theme_mode
    service = WebDataService(config, weather=weather, theme_mode=lambda: mode)
    server = create_server(config.http_server, None, service, StaticSite())
    if server is None:
        raise RuntimeError("HTTP server is disabled")  # enabled is forced on above
    print(f"Serving the web page on port {args.port}. Ctrl+C stops it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
