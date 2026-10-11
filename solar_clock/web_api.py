"""Data for the Solar Clock web page: the JSON behind GET /api/now.

Threading: the page is served by the single-threaded HTTPServer in
http_server.py, so one request runs at a time. That is what makes this
service's own SolarProvider and LunarProvider safe without locks
(LunarProvider moves a shared ephem.Observer on every call). Do not switch the
server to ThreadingHTTPServer without adding locking here. The TFT main loop
never touches these instances; the only provider shared with it is
WeatherProvider, which guards its own fetches.
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
from collections.abc import Callable
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .config import Config
from .data import LunarProvider, SolarProvider, WeatherProvider
from .data.solar import GoldenHour
from .views import colors
from .views.theme import DAY_THEME, NIGHT_THEME, Theme, ThemeManager, ThemeMode

logger = logging.getLogger(__name__)

# A runtime alias, so it uses Optional: Python 3.9 can't evaluate X | None.
Section = Optional[dict[str, Any]]


def hex_color(rgb: tuple[int, int, int]) -> str:
    """'#rrggbb' for an (r, g, b) tuple."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def iso(value: datetime.datetime | None, tz: datetime.tzinfo) -> str | None:
    """ISO 8601 text in the clock's timezone, or None."""
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError(f"naive datetime {value!r}: providers must return aware times")
    return value.astimezone(tz).isoformat(timespec="seconds")


def palette(theme: Theme) -> dict[str, str]:
    """Every colour field of a Theme as hex, keyed by field name."""
    return {
        key: hex_color(value)
        for key, value in dataclasses.asdict(theme).items()
        if key != "name"
    }


def named_colors() -> dict[str, str]:
    """The fixed colours exported by views/colors.py, e.g. {'PURPLE': '#9370db'}."""
    return {
        name: hex_color(value)
        for name, value in vars(colors).items()
        if name.isupper() and isinstance(value, tuple) and len(value) == 3
    }


class WebDataService:
    """Builds the JSON the web page polls. Read-only: never changes clock state."""

    def __init__(
        self,
        config: Config,
        weather: WeatherProvider | None,
        theme_mode: Callable[[], ThemeMode],
    ) -> None:
        """
        Args:
            config: Application configuration
            weather: The clock's shared WeatherProvider, or None without an API key
            theme_mode: Returns the clock's current theme mode; read, never set
        """
        loc = config.location
        self._config = config
        self._tz = ZoneInfo(loc.timezone)
        self._weather = weather
        self._theme_mode = theme_mode
        # Own instances, so the TFT's providers are never called from this thread.
        self._solar = SolarProvider(
            name=loc.name,
            region=loc.region,
            timezone=loc.timezone,
            latitude=loc.latitude,
            longitude=loc.longitude,
        )
        self._lunar = LunarProvider(
            latitude=loc.latitude, longitude=loc.longitude, timezone=loc.timezone
        )
        self._theme = ThemeManager(self._solar)  # not the singleton

    def build_now(self) -> dict[str, Any]:
        """Everything the phase 1 views need. A failing section becomes None."""
        return {
            "generated_at": datetime.datetime.now(self._tz).isoformat(
                timespec="seconds"
            ),
            "location": {
                "name": self._config.location.name,
                "timezone": self._config.location.timezone,
            },
            "units": self._config.weather.units,
            "theme": self._section("theme", self._theme_section),
            "sun": self._section("sun", self._sun_section),
            "weather": self._section("weather", self._weather_section),
            "air_quality": self._section("air_quality", self._air_quality_section),
            "moon": self._section("moon", self._moon_section),
        }

    @staticmethod
    def _section(name: str, build: Callable[[], Section]) -> Section:
        try:
            return build()
        except Exception:
            logger.exception("Web API section %r failed; sending null", name)
            return None

    def _theme_section(self) -> Section:
        mode = self._theme_mode()
        if mode != self._theme.mode:
            self._theme.set_mode(mode)  # our own instance; logs once per change
        return {
            "mode": mode,
            "active": self._theme.get_current_theme().name,
            "palettes": {"day": palette(DAY_THEME), "night": palette(NIGHT_THEME)},
            "colors": named_colors(),
        }

    def _sun_section(self) -> Section:
        times = self._solar.get_sun_times()
        if times is None:
            return None
        morning, evening = self._solar.get_golden_hour()
        position = self._solar.get_solar_position()
        next_event = self._solar.get_next_solar_event()
        return {
            "times": {
                key: iso(getattr(times, key), self._tz)
                for key in ("dawn", "sunrise", "noon", "sunset", "dusk")
            },
            "golden_hour": {
                "morning": self._span(morning),
                "evening": self._span(evening),
            },
            "position": (
                None
                if position is None
                else {
                    "elevation": round(position.elevation, 2),
                    "azimuth": round(position.azimuth, 2),
                }
            ),
            "day_length_hours": self._solar.get_day_length(),
            "day_length_change_min": self._solar.get_day_length_change(),
            "next_event": (
                None
                if next_event is None
                else {"name": next_event[0], "at": iso(next_event[1], self._tz)}
            ),
        }

    def _span(self, span: GoldenHour | None) -> Section:
        if span is None:
            return None
        return {"start": iso(span.start, self._tz), "end": iso(span.end, self._tz)}

    def _weather_section(self) -> Section:
        if self._weather is None:
            return None
        current = self._weather.get_current_weather()
        if current is None:
            return None
        forecast = self._weather.get_forecast(3) or []
        return {
            "current": dataclasses.asdict(current),
            "forecast": [dataclasses.asdict(day) for day in forecast],
        }

    def _air_quality_section(self) -> Section:
        if self._weather is None:
            return None
        aqi = self._weather.get_air_quality()
        if aqi is None:
            return None
        data = dataclasses.asdict(aqi)
        updated = datetime.datetime.fromtimestamp(aqi.updated_at, self._tz)
        data["updated_at"] = iso(updated, self._tz)
        return data

    def _moon_section(self) -> Section:
        if not self._lunar.available:
            return None
        phase = self._lunar.get_moon_phase()
        if phase is None:
            return None
        times = self._lunar.get_moon_times()
        return {
            "phase": {
                "phase": phase.phase,
                "illumination": phase.illumination,
                "phase_name": phase.phase_name,
                "next_new": phase.next_new.isoformat(),
                "next_full": phase.next_full.isoformat(),
                "days_to_new": phase.days_to_new,
                "days_to_full": phase.days_to_full,
            },
            "times": (
                None
                if times is None
                else {
                    "moonrise": iso(times.moonrise, self._tz),
                    "moonset": iso(times.moonset, self._tz),
                }
            ),
        }
