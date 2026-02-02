"""Views for Solar Smart Clock display."""

from .base import BaseView, ViewManager
from .clock import ClockView
from .weather import WeatherView
from .airquality import AirQualityView
from .sunpath import SunPathView
from .daylength import DayLengthView
from .solar import SolarView
from .moon import MoonView
from .analemma import AnalemmaView
from .analogclock import AnalogClockView
from .theme import Theme, ThemeManager, DAY_THEME, NIGHT_THEME, get_theme

# View order for navigation
VIEW_CLASSES = [
    ClockView,
    WeatherView,
    AirQualityView,
    SunPathView,
    DayLengthView,
    SolarView,
    MoonView,
    AnalemmaView,
    AnalogClockView,
]

__all__ = [
    "BaseView",
    "ViewManager",
    "VIEW_CLASSES",
    "ClockView",
    "WeatherView",
    "AirQualityView",
    "SunPathView",
    "DayLengthView",
    "SolarView",
    "MoonView",
    "AnalemmaView",
    "AnalogClockView",
    "Theme",
    "ThemeManager",
    "DAY_THEME",
    "NIGHT_THEME",
    "get_theme",
]
