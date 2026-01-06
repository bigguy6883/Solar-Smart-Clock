"""Tests for views."""

import datetime
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from solar_clock.config import Config
from solar_clock.views.base import BaseView, ViewManager, DataProviders
from solar_clock.views.clock import ClockView
from solar_clock.views.weather import WeatherView
from solar_clock.views.airquality import AirQualityView
from solar_clock.views.analogclock import AnalogClockView


class TestViewManager:
    """Tests for ViewManager."""

    @pytest.fixture
    def manager(self, sample_config, mock_providers):
        """Create a view manager with mock views."""
        views = [
            ClockView(sample_config, mock_providers),
            WeatherView(sample_config, mock_providers),
            AirQualityView(sample_config, mock_providers),
        ]
        return ViewManager(views, default_index=0)

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager.get_index() == 0
        assert manager.get_count() == 3
        assert manager.get_current() == "clock"

    def test_next_view(self, manager):
        """Test navigating to next view."""
        manager.next_view()
        assert manager.get_index() == 1
        assert manager.get_current() == "weather"

    def test_next_view_wraps(self, manager):
        """Test next view wraps around."""
        for _ in range(3):
            manager.next_view()
        assert manager.get_index() == 0  # Back to start

    def test_prev_view(self, manager):
        """Test navigating to previous view."""
        manager.next_view()  # Go to 1
        manager.prev_view()  # Back to 0
        assert manager.get_index() == 0

    def test_prev_view_wraps(self, manager):
        """Test prev view wraps around."""
        manager.prev_view()
        assert manager.get_index() == 2  # Last view

    def test_get_current_view(self, manager):
        """Test getting current view instance."""
        view = manager.get_current_view()
        assert isinstance(view, ClockView)

    def test_render_current(self, manager):
        """Test rendering current view."""
        image = manager.render_current()
        assert isinstance(image, Image.Image)
        assert image.size == (480, 320)


class TestBaseView:
    """Tests for BaseView functionality."""

    @pytest.fixture
    def clock_view(self, sample_config, mock_providers):
        """Create a clock view instance."""
        return ClockView(sample_config, mock_providers)

    def test_view_metadata(self, clock_view):
        """Test view has correct metadata."""
        assert clock_view.name == "clock"
        assert clock_view.title == "Clock"
        assert clock_view.update_interval >= 1

    def test_view_dimensions(self, clock_view):
        """Test view has correct dimensions."""
        assert clock_view.width == 480
        assert clock_view.height == 320
        assert clock_view.nav_height == 40
        assert clock_view.content_height == 280

    def test_get_font(self, clock_view):
        """Test font loading."""
        font = clock_view.get_font(16)
        assert font is not None

    def test_font_caching(self, clock_view):
        """Test fonts are cached."""
        font1 = clock_view.get_font(16)
        font2 = clock_view.get_font(16)
        assert font1 is font2  # Same object

    def test_render_produces_image(self, clock_view):
        """Test render produces valid image."""
        image = clock_view.render(0, 9)

        assert isinstance(image, Image.Image)
        assert image.mode == "RGB"
        assert image.size == (480, 320)

    def test_render_includes_nav_bar(self, clock_view):
        """Test rendered image includes navigation bar."""
        image = clock_view.render(0, 9)

        # Check that nav bar area has expected content
        # (nav buttons should be at bottom)
        pixels = image.load()
        # Bottom left corner should have nav button color (dark gray)
        bottom_left = pixels[30, 300]
        assert bottom_left != (0, 0, 0)  # Not pure black

    def test_time_header_color(self, clock_view):
        """Test time-based header color."""
        color = clock_view.get_time_header_color()
        assert isinstance(color, tuple)
        assert len(color) == 3
        assert all(0 <= c <= 255 for c in color)


class TestClockView:
    """Tests for ClockView."""

    @pytest.fixture
    def view(self, sample_config, mock_providers):
        """Create a clock view instance."""
        return ClockView(sample_config, mock_providers)

    def test_renders_time(self, view):
        """Test clock view renders current time."""
        image = view.render(0, 9)

        # Convert to string to check it contains something
        # (hard to check specific text without OCR)
        assert image is not None


class TestWeatherView:
    """Tests for WeatherView."""

    @pytest.fixture
    def view(self, sample_config, mock_providers):
        """Create a weather view instance."""
        return WeatherView(sample_config, mock_providers)

    def test_renders_weather(self, view):
        """Test weather view renders."""
        image = view.render(1, 9)
        assert image is not None
        assert image.size == (480, 320)

    def test_renders_without_data(self, sample_config):
        """Test weather view renders even without weather data."""
        providers = DataProviders(weather=None, solar=None, lunar=None)
        view = WeatherView(sample_config, providers)

        image = view.render(1, 9)
        assert image is not None


class TestAirQualityView:
    """Tests for AirQualityView."""

    @pytest.fixture
    def view(self, sample_config, mock_providers):
        """Create an air quality view instance."""
        return AirQualityView(sample_config, mock_providers)

    def test_aqi_colors(self, view):
        """Test AQI color mapping."""
        assert view._get_aqi_color(25) == (0, 228, 0)  # Good - green
        assert view._get_aqi_color(75) == (255, 255, 0)  # Moderate - yellow
        assert view._get_aqi_color(350) == (126, 0, 35)  # Hazardous - maroon


class TestAnalogClockView:
    """Tests for AnalogClockView."""

    @pytest.fixture
    def view(self, sample_config, mock_providers):
        """Create an analog clock view instance."""
        return AnalogClockView(sample_config, mock_providers)

    def test_renders_clock_face(self, view):
        """Test analog clock renders."""
        image = view.render(8, 9)
        assert image is not None
        assert image.size == (480, 320)

    def test_update_interval_fast(self, view):
        """Test analog clock updates every second."""
        assert view.update_interval == 1
