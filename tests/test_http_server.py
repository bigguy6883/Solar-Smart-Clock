"""Tests for HTTP server and API endpoints."""

import base64
import os
import time
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

import pytest
from PIL import Image

from solar_clock.http_server import (
    RateLimiter,
    ScreenshotHandler,
    create_server,
    start_server_thread,
)


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_rate_limiter_allows_initial_requests(self):
        """Test that rate limiter allows requests initially."""
        limiter = RateLimiter(rate_per_second=10)
        assert limiter.allow() is True

    def test_rate_limiter_blocks_excessive_requests(self):
        """Test that rate limiter blocks too many requests."""
        limiter = RateLimiter(rate_per_second=2)

        # First two should pass
        assert limiter.allow() is True
        assert limiter.allow() is True

        # Third should be blocked
        assert limiter.allow() is False

    def test_rate_limiter_refills_over_time(self):
        """Test that rate limiter refills tokens over time."""
        limiter = RateLimiter(rate_per_second=10)

        # Exhaust tokens
        for _ in range(10):
            limiter.allow()

        # Should be blocked
        assert limiter.allow() is False

        # Wait for refill (0.2 seconds = 2 tokens at 10/sec)
        time.sleep(0.2)

        # Should allow again
        assert limiter.allow() is True

    def test_rate_limiter_caps_at_max_rate(self):
        """Test that rate limiter doesn't accumulate tokens indefinitely."""
        limiter = RateLimiter(rate_per_second=5)

        # Wait for more than 1 second
        time.sleep(1.5)

        # Should only have 5 tokens max, not 7.5
        allowed_count = 0
        for _ in range(10):
            if limiter.allow():
                allowed_count += 1

        assert allowed_count <= 5


class TestScreenshotHandler:
    """Tests for the ScreenshotHandler class."""

    @pytest.fixture
    def mock_clock(self):
        """Create a mock clock instance."""
        clock = MagicMock()

        # Mock view manager
        clock.view_manager = MagicMock()
        clock.view_manager.get_current.return_value = "clock"
        clock.view_manager.get_index.return_value = 0
        clock.view_manager.get_count.return_value = 9

        # Mock frame rendering
        frame = Image.new("RGB", (480, 320), color=(0, 0, 0))
        clock.view_manager.render_current.return_value = frame
        clock.get_last_frame.return_value = frame

        return clock

    @pytest.fixture
    def handler_with_mock(self, mock_clock):
        """Create a handler instance with mocked dependencies."""
        # Reset class attributes (accessed via self in the handler)
        ScreenshotHandler.clock_instance = mock_clock
        ScreenshotHandler.rate_limiter = None
        ScreenshotHandler.auth_credentials = None

        # Create handler without going through __init__
        # to avoid socket/request parsing
        handler = object.__new__(ScreenshotHandler)
        handler.path = "/"
        handler.headers = {}
        handler.wfile = BytesIO()
        handler.client_address = ("127.0.0.1", 12345)

        return handler

    def test_health_endpoint(self, handler_with_mock):
        """Test /health endpoint returns OK."""
        handler = handler_with_mock
        handler.path = "/health"

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(200)
        assert b"OK" in handler.wfile.getvalue()

    def test_screenshot_endpoint(self, handler_with_mock):
        """Test /screenshot endpoint returns PNG image."""
        handler = handler_with_mock
        handler.path = "/screenshot"

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(200)
        # Check that PNG header is present
        output = handler.wfile.getvalue()
        assert output.startswith(b"\x89PNG")

    def test_screenshot_no_frame_available(self, handler_with_mock, mock_clock):
        """Test /screenshot when no frame is available."""
        handler = handler_with_mock
        handler.path = "/screenshot"

        # Mock no frame available
        mock_clock.view_manager.render_current.return_value = None
        mock_clock.get_last_frame.return_value = None

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(503)
        assert b"No frame available" in handler.wfile.getvalue()

    def test_screenshot_clock_not_initialized(self, handler_with_mock):
        """Test /screenshot when clock is not initialized."""
        handler = handler_with_mock
        handler.path = "/screenshot"
        ScreenshotHandler.clock_instance = None

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(503)
        assert b"Clock not initialized" in handler.wfile.getvalue()

    def test_next_endpoint(self, handler_with_mock, mock_clock):
        """Test /next endpoint navigates to next view."""
        handler = handler_with_mock
        handler.path = "/next"

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        mock_clock.view_manager.next_view.assert_called_once()
        handler.send_response.assert_called_with(200)
        assert b"clock (1/9)" in handler.wfile.getvalue()

    def test_prev_endpoint(self, handler_with_mock, mock_clock):
        """Test /prev endpoint navigates to previous view."""
        handler = handler_with_mock
        handler.path = "/prev"

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        mock_clock.view_manager.prev_view.assert_called_once()
        handler.send_response.assert_called_with(200)
        assert b"clock (1/9)" in handler.wfile.getvalue()

    def test_view_endpoint(self, handler_with_mock, mock_clock):
        """Test /view endpoint returns current view info."""
        handler = handler_with_mock
        handler.path = "/view"

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(200)
        assert b"clock (1/9)" in handler.wfile.getvalue()

    def test_not_found_endpoint(self, handler_with_mock):
        """Test unknown endpoint returns 404."""
        handler = handler_with_mock
        handler.path = "/invalid"

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(404)
        assert b"Not Found" in handler.wfile.getvalue()

    def test_rate_limiting(self, handler_with_mock):
        """Test that rate limiting blocks excessive requests."""
        handler = handler_with_mock
        handler.path = "/health"
        ScreenshotHandler.rate_limiter = RateLimiter(rate_per_second=1)

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        # First request should succeed
        handler.do_GET()
        assert handler.send_response.call_args[0][0] == 200

        # Reset mocks and wfile
        handler.send_response.reset_mock()
        handler.wfile = BytesIO()

        # Second immediate request should be rate limited
        handler.do_GET()
        assert handler.send_response.call_args[0][0] == 429
        assert b"Too Many Requests" in handler.wfile.getvalue()

    def test_basic_auth_success(self, handler_with_mock):
        """Test successful basic authentication."""
        handler = handler_with_mock
        handler.path = "/health"

        # Set up auth credentials
        ScreenshotHandler.auth_credentials = ("testuser", "testpass")

        # Create valid auth header
        credentials = base64.b64encode(b"testuser:testpass").decode("utf-8")
        handler.headers = {"Authorization": f"Basic {credentials}"}

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(200)
        assert b"OK" in handler.wfile.getvalue()

    def test_basic_auth_failure_wrong_password(self, handler_with_mock):
        """Test basic authentication with wrong password."""
        handler = handler_with_mock
        handler.path = "/health"

        # Set up auth credentials
        ScreenshotHandler.auth_credentials = ("testuser", "testpass")

        # Create invalid auth header
        credentials = base64.b64encode(b"testuser:wrongpass").decode("utf-8")
        handler.headers = {"Authorization": f"Basic {credentials}"}

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(401)
        assert b"Unauthorized" in handler.wfile.getvalue()

    def test_basic_auth_failure_no_header(self, handler_with_mock):
        """Test basic authentication without auth header."""
        handler = handler_with_mock
        handler.path = "/health"

        # Set up auth credentials
        ScreenshotHandler.auth_credentials = ("testuser", "testpass")
        handler.headers = {}

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(401)
        assert b"Unauthorized" in handler.wfile.getvalue()

    def test_basic_auth_failure_malformed(self, handler_with_mock):
        """Test basic authentication with malformed header."""
        handler = handler_with_mock
        handler.path = "/health"

        # Set up auth credentials
        ScreenshotHandler.auth_credentials = ("testuser", "testpass")

        # Malformed header (not base64)
        handler.headers = {"Authorization": "Basic invalid!@#$"}

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        handler.send_response.assert_called_with(401)

    def test_no_auth_when_not_configured(self, handler_with_mock):
        """Test that requests are allowed when auth is not configured."""
        handler = handler_with_mock
        handler.path = "/health"

        # No auth credentials set
        ScreenshotHandler.auth_credentials = None
        handler.headers = {}

        # Mock send methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        handler.do_GET()

        # Should succeed without auth
        handler.send_response.assert_called_with(200)


class TestServerCreation:
    """Tests for server creation and configuration."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock HTTP server config."""
        config = MagicMock()
        config.enabled = True
        config.port = 8080
        config.bind_address = "127.0.0.1"
        config.rate_limit_per_second = 10
        return config

    def test_create_server_disabled(self, mock_config):
        """Test that None is returned when server is disabled."""
        mock_config.enabled = False
        server = create_server(mock_config, MagicMock())
        assert server is None

    def test_create_server_enabled(self, mock_config):
        """Test server creation when enabled."""
        clock = MagicMock()
        server = create_server(mock_config, clock)

        assert server is not None
        assert ScreenshotHandler.clock_instance == clock
        assert ScreenshotHandler.rate_limiter is not None

    @patch.dict(os.environ, {"HTTP_AUTH_USER": "admin", "HTTP_AUTH_PASS": "secret"})
    def test_create_server_with_auth(self, mock_config):
        """Test server creation with auth credentials from environment."""
        clock = MagicMock()
        server = create_server(mock_config, clock)

        assert server is not None
        assert ScreenshotHandler.auth_credentials == ("admin", "secret")

    @patch.dict(os.environ, {}, clear=True)
    def test_create_server_without_auth(self, mock_config):
        """Test server creation without auth credentials."""
        clock = MagicMock()
        server = create_server(mock_config, clock)

        assert server is not None
        assert ScreenshotHandler.auth_credentials is None

    def test_start_server_thread(self, mock_config):
        """Test starting server in daemon thread."""
        clock = MagicMock()
        server = create_server(mock_config, clock)

        thread = start_server_thread(server)

        assert thread is not None
        assert thread.daemon is True
        assert thread.is_alive()

        # Clean up
        server.shutdown()
        thread.join(timeout=1)
