"""Tests for views."""

import datetime
import pytest
from unittest.mock import MagicMock
from PIL import Image

from solar_clock.views.base import ViewManager, DataProviders
from solar_clock.views.clock import ClockView
from solar_clock.views.weather import WeatherView
from solar_clock.views.airquality import AirQualityView
from solar_clock.views.analogclock import AnalogClockView
from solar_clock.views.sunpath import SunPathView
from solar_clock.views.daylength import DayLengthView
from solar_clock.views.moon import MoonView
from solar_clock.views.solar import SolarView
from solar_clock.views.analemma import AnalemmaView


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


class TestSunPathView:
    """Tests for SunPathView."""

    @pytest.fixture
    def view(self, sample_config, mock_providers):
        """Create a sun path view instance."""
        return SunPathView(sample_config, mock_providers)

    def test_renders(self, view):
        """Test sun path view renders."""
        image = view.render(3, 9)
        assert image is not None
        assert image.size == (480, 320)

    def test_view_metadata(self, view):
        """Test sun path view has correct metadata."""
        assert view.name == "sunpath"
        assert view.title == "Sun Path"


class TestDayLengthView:
    """Tests for DayLengthView."""

    @pytest.fixture
    def view(self, sample_config, mock_providers):
        """Create a day length view instance."""
        return DayLengthView(sample_config, mock_providers)

    def test_renders(self, view):
        """Test day length view renders."""
        image = view.render(4, 9)
        assert image is not None
        assert image.size == (480, 320)

    def test_view_metadata(self, view):
        """Test day length view has correct metadata."""
        assert view.name == "daylength"
        assert view.title == "Day Length"


class TestMoonView:
    """Tests for MoonView."""

    @pytest.fixture
    def view(self, sample_config, mock_providers):
        """Create a moon view instance."""
        return MoonView(sample_config, mock_providers)

    def test_renders(self, view):
        """Test moon view renders."""
        image = view.render(6, 9)
        assert image is not None
        assert image.size == (480, 320)

    def test_view_metadata(self, view):
        """Test moon view has correct metadata."""
        assert view.name == "moon"
        assert view.title == "Moon Phase"

    def test_renders_without_lunar_data(self, sample_config):
        """Test moon view renders without lunar provider."""
        providers = DataProviders(weather=None, solar=None, lunar=None)
        view = MoonView(sample_config, providers)

        image = view.render(6, 9)
        assert image is not None


class TestSolarView:
    """Tests for SolarView."""

    @pytest.fixture
    def view(self, sample_config, mock_providers):
        """Create a solar view instance."""
        return SolarView(sample_config, mock_providers)

    def test_renders(self, view):
        """Test solar view renders."""
        image = view.render(5, 9)
        assert image is not None
        assert image.size == (480, 320)

    def test_view_metadata(self, view):
        """Test solar view has correct metadata."""
        assert view.name == "solar"
        assert view.title == "Solar Details"


class TestAnalemmaView:
    """Tests for AnalemmaView."""

    @pytest.fixture
    def view(self, sample_config, mock_providers):
        """Create an analemma view instance."""
        return AnalemmaView(sample_config, mock_providers)

    def test_renders(self, view):
        """Test analemma view renders."""
        image = view.render(7, 9)
        assert image is not None
        assert image.size == (480, 320)

    def test_view_metadata(self, view):
        """Test analemma view has correct metadata."""
        assert view.name == "analemma"
        assert view.title == "Analemma"

    def test_renders_without_lunar_data(self, sample_config):
        """Test analemma view renders without lunar provider."""
        providers = DataProviders(weather=None, solar=None, lunar=None)
        view = AnalemmaView(sample_config, providers)

        image = view.render(7, 9)
        assert image is not None


def _collect_drawn_text(view, render_index=0, total_views=9):
    """Render a view and return all text strings passed to draw.text()."""
    drawn = []
    original_render_content = view.render_content

    def capturing_render_content(draw, image):
        original_text = draw.text

        def capture_text(xy, text, **kwargs):
            drawn.append(text)
            return original_text(xy, text, **kwargs)

        draw.text = capture_text
        original_render_content(draw, image)
        draw.text = original_text

    view.render_content = capturing_render_content
    view.render(render_index, total_views)
    return drawn


class TestNegativeCountdownGuard:
    """Tests that past solar events do not produce negative countdown text."""

    def _make_past_event_providers(self, sample_config):
        """Build providers where get_next_solar_event returns a time 5 seconds in the past."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/New_York")
        past_time = datetime.datetime.now(tz) - datetime.timedelta(seconds=5)

        solar = MagicMock()
        solar.get_sun_times.return_value = MagicMock(
            dawn=datetime.datetime(2024, 1, 15, 6, 30, tzinfo=tz),
            sunrise=datetime.datetime(2024, 1, 15, 7, 0, tzinfo=tz),
            noon=datetime.datetime(2024, 1, 15, 12, 30, tzinfo=tz),
            sunset=datetime.datetime(2024, 1, 15, 17, 30, tzinfo=tz),
            dusk=datetime.datetime(2024, 1, 15, 18, 0, tzinfo=tz),
        )
        solar.get_day_length.return_value = 10.5
        solar.get_day_length_change.return_value = 1.5
        solar.get_solar_position.return_value = MagicMock(elevation=35.5, azimuth=180.0)
        solar.get_golden_hour.return_value = (
            MagicMock(
                start=datetime.datetime(2024, 1, 15, 6, 30, tzinfo=tz),
                end=datetime.datetime(2024, 1, 15, 7, 30, tzinfo=tz),
            ),
            MagicMock(
                start=datetime.datetime(2024, 1, 15, 17, 0, tzinfo=tz),
                end=datetime.datetime(2024, 1, 15, 18, 0, tzinfo=tz),
            ),
        )
        # Past event: 5 seconds ago
        solar.get_next_solar_event.return_value = ("Sunrise", past_time)

        weather = MagicMock()
        weather.get_current_weather.return_value = MagicMock(
            temperature=72.5,
            feels_like=70.0,
            humidity=65,
            description="Partly Cloudy",
            wind_speed=5.5,
            wind_direction="S",
        )

        lunar = MagicMock()
        lunar.available = True

        return DataProviders(weather=weather, solar=solar, lunar=lunar)

    def test_clock_view_no_negative_countdown(self, sample_config):
        """ClockView must not render a negative countdown when event is in the past."""
        providers = self._make_past_event_providers(sample_config)
        view = ClockView(sample_config, providers)
        drawn = _collect_drawn_text(view, render_index=0)

        negative_texts = [t for t in drawn if "in -" in str(t)]
        assert (
            negative_texts == []
        ), f"ClockView drew negative countdown text: {negative_texts}"

    def test_solar_view_no_negative_countdown(self, sample_config):
        """SolarView must not render a negative countdown when event is in the past."""
        providers = self._make_past_event_providers(sample_config)
        view = SolarView(sample_config, providers)
        drawn = _collect_drawn_text(view, render_index=5)

        negative_texts = [t for t in drawn if "in -" in str(t)]
        assert (
            negative_texts == []
        ), f"SolarView drew negative countdown text: {negative_texts}"

    def test_sunpath_view_no_negative_countdown(self, sample_config):
        """SunPathView must not render a negative countdown when event is in the past."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/New_York")
        providers = self._make_past_event_providers(sample_config)
        # Also make solar noon in the past so the fallback path (get_next_solar_event) is used
        past_noon = datetime.datetime.now(tz) - datetime.timedelta(hours=1)
        providers.solar.get_sun_times.return_value = MagicMock(
            dawn=datetime.datetime(2024, 1, 15, 6, 30, tzinfo=tz),
            sunrise=datetime.datetime(2024, 1, 15, 7, 0, tzinfo=tz),
            noon=past_noon,
            sunset=datetime.datetime(2024, 1, 15, 17, 30, tzinfo=tz),
            dusk=datetime.datetime(2024, 1, 15, 18, 0, tzinfo=tz),
        )
        view = SunPathView(sample_config, providers)
        drawn = _collect_drawn_text(view, render_index=3)

        negative_texts = [t for t in drawn if "in -" in str(t)]
        assert (
            negative_texts == []
        ), f"SunPathView drew negative countdown text: {negative_texts}"
