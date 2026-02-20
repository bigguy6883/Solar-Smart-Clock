"""Tests for main application lifecycle and SolarClock class."""

import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from solar_clock.main import SolarClock, main


class TestSolarClock:
    """Tests for the SolarClock class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock()

        # Location config
        config.location.name = "Test City"
        config.location.region = "Test Region"
        config.location.timezone = "America/New_York"
        config.location.latitude = 40.7128
        config.location.longitude = -74.0060

        # Display config
        config.display.width = 480
        config.display.height = 320
        config.display.framebuffer = "/dev/fb1"
        config.display.nav_bar_height = 40

        # HTTP server config
        config.http_server.enabled = True
        config.http_server.port = 8080
        config.http_server.bind_address = "127.0.0.1"
        config.http_server.rate_limit_per_second = 10

        # Weather config
        config.weather.units = "imperial"
        config.weather.update_interval_seconds = 900

        # Air quality config
        config.air_quality.update_interval_seconds = 1800

        # Touch config
        config.touch.enabled = True
        config.touch.device = "/dev/input/event0"

        # Appearance config
        config.appearance.default_view = 0
        config.appearance.theme_mode = "auto"

        return config

    @pytest.fixture
    def solar_clock(self, mock_config):
        """Create a SolarClock instance with mocked dependencies."""
        with patch("solar_clock.main.get_api_key", return_value="test_api_key"):
            with patch("solar_clock.main.WeatherProvider"):
                with patch("solar_clock.main.SolarProvider"):
                    with patch("solar_clock.main.LunarProvider"):
                        with patch("solar_clock.main.VIEW_CLASSES", []):
                            with patch("solar_clock.main.ViewManager"):
                                with patch("solar_clock.main.Display"):
                                    with patch("solar_clock.main.create_server"):
                                        with patch("solar_clock.main.TouchHandler"):
                                            with patch(
                                                "solar_clock.main.ThemeManager"
                                            ) as mock_theme:
                                                mock_theme.initialize.return_value = (
                                                    MagicMock()
                                                )
                                                clock = SolarClock(mock_config)
        return clock

    def test_initialization(self, solar_clock, mock_config):
        """Test SolarClock initialization."""
        assert solar_clock.config == mock_config
        assert solar_clock.running is False
        assert solar_clock._last_frame is None
        assert solar_clock.providers is not None
        assert solar_clock.view_manager is not None
        assert solar_clock.display is not None
        assert solar_clock.touch_handler is not None

    def test_initialization_with_api_key(self, mock_config):
        """Test initialization creates WeatherProvider with API key."""
        with patch("solar_clock.main.get_api_key", return_value="test_key"):
            with patch("solar_clock.main.WeatherProvider") as mock_weather:
                with patch("solar_clock.main.SolarProvider"):
                    with patch("solar_clock.main.LunarProvider"):
                        with patch("solar_clock.main.VIEW_CLASSES", []):
                            with patch("solar_clock.main.ViewManager"):
                                with patch("solar_clock.main.Display"):
                                    with patch("solar_clock.main.create_server"):
                                        with patch("solar_clock.main.TouchHandler"):
                                            with patch(
                                                "solar_clock.main.ThemeManager"
                                            ) as mock_theme:
                                                mock_theme.initialize.return_value = (
                                                    MagicMock()
                                                )
                                                SolarClock(mock_config)

        mock_weather.assert_called_once()
        call_kwargs = mock_weather.call_args[1]
        assert call_kwargs["api_key"] == "test_key"
        assert call_kwargs["latitude"] == 40.7128
        assert call_kwargs["longitude"] == -74.0060

    def test_initialization_without_api_key(self, mock_config):
        """Test initialization without API key sets weather provider to None."""
        with patch("solar_clock.main.get_api_key", return_value=None):
            with patch("solar_clock.main.SolarProvider"):
                with patch("solar_clock.main.LunarProvider"):
                    with patch("solar_clock.main.VIEW_CLASSES", []):
                        with patch("solar_clock.main.ViewManager"):
                            with patch("solar_clock.main.Display"):
                                with patch("solar_clock.main.create_server"):
                                    with patch("solar_clock.main.TouchHandler"):
                                        with patch(
                                            "solar_clock.main.ThemeManager"
                                        ) as mock_theme:
                                            mock_theme.initialize.return_value = (
                                                MagicMock()
                                            )
                                            test_clock = SolarClock(mock_config)

        assert test_clock.providers.weather is None

    def test_get_last_frame(self, solar_clock):
        """Test get_last_frame returns cached frame."""
        test_frame = Image.new("RGB", (480, 320))
        solar_clock._last_frame = test_frame

        result = solar_clock.get_last_frame()

        assert result is test_frame

    def test_get_last_frame_when_none(self, solar_clock):
        """Test get_last_frame returns None when no frame cached."""
        solar_clock._last_frame = None

        result = solar_clock.get_last_frame()

        assert result is None

    def test_signal_handler_stops_running(self, solar_clock):
        """Test signal handler sets running to False."""
        solar_clock.running = True

        solar_clock._signal_handler(signal.SIGINT, None)

        assert solar_clock.running is False

    def test_signal_handler_wakes_main_loop(self):
        """Signal handler must set view_changed to interrupt the sleep."""
        import threading
        from solar_clock.main import SolarClock
        from unittest.mock import MagicMock

        clock = SolarClock.__new__(SolarClock)
        clock.running = True
        clock.view_manager = MagicMock()
        clock.view_manager.view_changed = threading.Event()

        clock._signal_handler(2, None)

        assert not clock.running
        assert (
            clock.view_manager.view_changed.is_set()
        ), "view_changed must be set so wait() returns immediately"

    def test_cleanup(self, solar_clock):
        """Test cleanup stops all components."""
        # Setup mocks
        solar_clock.touch_handler = MagicMock()
        solar_clock.http_server = MagicMock()
        solar_clock.display = MagicMock()

        solar_clock._cleanup()

        solar_clock.touch_handler.stop.assert_called_once()
        solar_clock.http_server.shutdown.assert_called_once()
        solar_clock.display.close.assert_called_once()

    def test_cleanup_without_http_server(self, solar_clock):
        """Test cleanup works when HTTP server is None."""
        solar_clock.touch_handler = MagicMock()
        solar_clock.http_server = None
        solar_clock.display = MagicMock()

        # Should not raise exception
        solar_clock._cleanup()

        solar_clock.touch_handler.stop.assert_called_once()
        solar_clock.display.close.assert_called_once()

    @patch("solar_clock.main.start_server_thread")
    def test_run_opens_display(self, mock_start_thread, solar_clock):
        """Test run opens display."""
        solar_clock.display = MagicMock()
        solar_clock.display.open.return_value = False

        solar_clock.run()

        solar_clock.display.open.assert_called_once()

    @patch("solar_clock.main.start_server_thread")
    def test_run_exits_if_display_fails(self, mock_start_thread, solar_clock):
        """Test run exits if display fails to open."""
        solar_clock.display = MagicMock()
        solar_clock.display.open.return_value = False
        solar_clock.touch_handler = MagicMock()

        solar_clock.run()

        # Should not start touch handler if display fails
        solar_clock.touch_handler.start.assert_not_called()

    @patch("solar_clock.main.start_server_thread")
    @patch("solar_clock.main.signal.signal")
    def test_run_starts_http_server(self, mock_signal, mock_start_thread, solar_clock):
        """Test run starts HTTP server if configured."""
        solar_clock.display = MagicMock()
        solar_clock.display.open.return_value = True
        solar_clock.http_server = MagicMock()
        solar_clock.http_thread = None
        solar_clock.touch_handler = MagicMock()
        solar_clock.view_manager = MagicMock()
        solar_clock.running = True

        # Make the loop exit immediately
        def stop_running(*args, **kwargs):
            solar_clock.running = False
            return Image.new("RGB", (480, 320))

        solar_clock.view_manager.render_current.side_effect = stop_running

        solar_clock.run()

        mock_start_thread.assert_called_once_with(solar_clock.http_server)

    @patch("solar_clock.main.start_server_thread")
    @patch("solar_clock.main.signal.signal")
    def test_run_starts_touch_handler(
        self, mock_signal, mock_start_thread, solar_clock
    ):
        """Test run starts touch handler."""
        solar_clock.display = MagicMock()
        solar_clock.display.open.return_value = True
        solar_clock.http_server = None
        solar_clock.touch_handler = MagicMock()
        solar_clock.view_manager = MagicMock()
        solar_clock.running = True

        # Make the loop exit immediately
        def stop_running(*args, **kwargs):
            solar_clock.running = False
            return Image.new("RGB", (480, 320))

        solar_clock.view_manager.render_current.side_effect = stop_running

        solar_clock.run()

        solar_clock.touch_handler.start.assert_called_once()

    @patch("solar_clock.main.start_server_thread")
    @patch("solar_clock.main.signal.signal")
    def test_run_registers_signal_handlers(
        self, mock_signal, mock_start_thread, solar_clock
    ):
        """Test run registers SIGINT and SIGTERM handlers."""
        solar_clock.display = MagicMock()
        solar_clock.display.open.return_value = True
        solar_clock.touch_handler = MagicMock()
        solar_clock.view_manager = MagicMock()
        solar_clock.running = True

        # Make the loop exit immediately
        def stop_running(*args, **kwargs):
            solar_clock.running = False
            return Image.new("RGB", (480, 320))

        solar_clock.view_manager.render_current.side_effect = stop_running

        solar_clock.run()

        # Check signal handlers were registered
        assert mock_signal.call_count >= 2
        signal_calls = [call[0][0] for call in mock_signal.call_args_list]
        assert signal.SIGINT in signal_calls
        assert signal.SIGTERM in signal_calls

    @patch("solar_clock.main.start_server_thread")
    @patch("solar_clock.main.signal.signal")
    def test_run_main_loop_renders_and_displays(
        self, mock_signal, mock_start_thread, solar_clock
    ):
        """Test main loop renders view and writes to display."""
        solar_clock.display = MagicMock()
        solar_clock.display.open.return_value = True
        solar_clock.touch_handler = MagicMock()
        solar_clock.view_manager = MagicMock()

        test_frame = Image.new("RGB", (480, 320))
        solar_clock.view_manager.render_current.return_value = test_frame

        # Run one iteration then stop
        iteration_count = [0]

        def render_with_counter():
            iteration_count[0] += 1
            if iteration_count[0] > 1:
                solar_clock.running = False
            return test_frame

        solar_clock.view_manager.render_current.side_effect = render_with_counter
        solar_clock.running = True

        solar_clock.run()

        # Verify render and write were called
        assert solar_clock.view_manager.render_current.call_count >= 1
        assert solar_clock.display.write_frame.call_count >= 1
        assert solar_clock._last_frame is test_frame

    @patch("solar_clock.main.start_server_thread")
    @patch("solar_clock.main.signal.signal")
    def test_run_cleanup_on_exception(
        self, mock_signal, mock_start_thread, solar_clock
    ):
        """Test cleanup is called even if exception occurs."""
        solar_clock.display = MagicMock()
        solar_clock.display.open.return_value = True
        solar_clock.touch_handler = MagicMock()
        solar_clock.view_manager = MagicMock()
        solar_clock.view_manager.render_current.side_effect = RuntimeError("Test error")
        solar_clock.running = True

        solar_clock.run()

        # Cleanup should have been called
        solar_clock.display.close.assert_called_once()


class TestMainFunction:
    """Tests for the main() entry point function."""

    @patch("solar_clock.main.SolarClock")
    @patch("solar_clock.main.load_config")
    @patch("solar_clock.main.get_api_key", return_value="test_key")
    @patch("sys.argv", ["solar_clock"])
    def test_main_success(self, mock_get_key, mock_load_config, mock_solar_clock):
        """Test successful main execution."""
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        result = main()

        assert result == 0
        mock_load_config.assert_called_once()
        mock_solar_clock.assert_called_once_with(mock_config)
        mock_solar_clock.return_value.run.assert_called_once()

    @patch("solar_clock.main.load_config")
    @patch("sys.argv", ["solar_clock"])
    def test_main_config_not_found(self, mock_load_config):
        """Test main returns 1 when config file not found."""
        mock_load_config.side_effect = FileNotFoundError("Config not found")

        result = main()

        assert result == 1

    @patch("solar_clock.main.load_config")
    @patch("sys.argv", ["solar_clock"])
    def test_main_invalid_config(self, mock_load_config):
        """Test main returns 1 when config is invalid."""
        mock_load_config.side_effect = ValueError("Invalid config")

        result = main()

        assert result == 1

    @patch("solar_clock.main.SolarClock")
    @patch("solar_clock.main.load_config")
    @patch("solar_clock.main.get_api_key", return_value="test_key")
    @patch("sys.argv", ["solar_clock", "-c", "/path/to/config.json"])
    def test_main_with_config_path(
        self, mock_get_key, mock_load_config, mock_solar_clock
    ):
        """Test main with custom config path."""
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        result = main()

        assert result == 0
        # Check that config path was passed
        assert mock_load_config.call_args[0][0] == Path("/path/to/config.json")

    @patch("solar_clock.main.SolarClock")
    @patch("solar_clock.main.load_config")
    @patch("solar_clock.main.get_api_key", return_value="test_key")
    @patch("logging.getLogger")
    @patch("sys.argv", ["solar_clock", "-v"])
    def test_main_with_verbose(
        self, mock_get_logger, mock_get_key, mock_load_config, mock_solar_clock
    ):
        """Test main with verbose logging."""
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        result = main()

        assert result == 0

    @patch("solar_clock.main.SolarClock")
    @patch("solar_clock.main.load_config")
    @patch("solar_clock.main.get_api_key", return_value="test_key")
    @patch("sys.argv", ["solar_clock", "--bind-all"])
    def test_main_with_bind_all(self, mock_get_key, mock_load_config, mock_solar_clock):
        """Test main with --bind-all flag."""
        mock_config = MagicMock()
        mock_config.http_server.bind_address = "127.0.0.1"
        mock_load_config.return_value = mock_config

        result = main()

        assert result == 0
        assert mock_config.http_server.bind_address == "0.0.0.0"

    @patch("solar_clock.main.SolarClock")
    @patch("solar_clock.main.load_config")
    @patch("solar_clock.main.get_api_key", return_value=None)
    @patch("sys.argv", ["solar_clock"])
    def test_main_without_api_key(
        self, mock_get_key, mock_load_config, mock_solar_clock
    ):
        """Test main warns when API key is not set."""
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        result = main()

        # Should still run successfully without API key
        assert result == 0
        mock_solar_clock.assert_called_once()
