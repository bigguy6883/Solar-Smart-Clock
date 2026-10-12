"""Tests for HTTP server and API endpoints."""

import base64
import json
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
from solar_clock.web_static import StaticSite


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
        # Port 0 = OS-assigned ephemeral port; avoids conflicts with anything
        # already bound on the dev machine (e.g. another service on 8080).
        config.port = 0
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


def _request(path, request_headers=None):
    """Run one GET through ScreenshotHandler; return (status, headers, body)."""
    handler = object.__new__(ScreenshotHandler)
    handler.path = path
    handler.headers = request_headers or {}
    handler.wfile = BytesIO()
    handler.client_address = ("127.0.0.1", 12345)
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()
    handler.do_GET()
    status = handler.send_response.call_args[0][0]
    headers = {c[0][0]: c[0][1] for c in handler.send_header.call_args_list}
    return status, headers, handler.wfile.getvalue()


class TestWebPageRoutes:
    """The web page: its static files and /api/now."""

    @pytest.fixture
    def site_root(self, tmp_path):
        root = tmp_path / "web"
        (root / "js").mkdir(parents=True)
        (root / "index.html").write_text("<!doctype html><title>Solar Clock</title>")
        (root / "style.css").write_text("body {}")
        (root / "js" / "app.js").write_text("export {};")
        (root / "manifest.webmanifest").write_text("{}")
        (root / "notes.txt").write_text("not on the allowlist")
        (tmp_path / "config.json").write_text('{"secret": "coordinates"}')
        return root

    @pytest.fixture(autouse=True)
    def web_handler(self, site_root):
        ScreenshotHandler.clock_instance = MagicMock()
        ScreenshotHandler.rate_limiter = None
        ScreenshotHandler.auth_credentials = None
        ScreenshotHandler.static_site = StaticSite(site_root)
        ScreenshotHandler.web_service = MagicMock()
        ScreenshotHandler.web_service.build_now.return_value = {"sun": None}
        yield
        ScreenshotHandler.static_site = None
        ScreenshotHandler.web_service = None
        ScreenshotHandler.auth_credentials = None

    def test_root_serves_index_html(self):
        status, headers, body = _request("/")
        assert status == 200
        assert headers["Content-Type"] == "text/html; charset=utf-8"
        assert headers["Cache-Control"] == "no-cache"
        assert b"Solar Clock" in body

    def test_root_ignores_a_query_string(self):
        status, _, body = _request("/?from=homescreen")
        assert status == 200
        assert b"Solar Clock" in body

    @pytest.mark.parametrize(
        "path, content_type",
        [
            ("/style.css", "text/css; charset=utf-8"),
            ("/js/app.js", "text/javascript; charset=utf-8"),
            ("/manifest.webmanifest", "application/manifest+json"),
        ],
    )
    def test_static_files_have_the_right_type(self, path, content_type):
        status, headers, _ = _request(path)
        assert status == 200
        assert headers["Content-Type"] == content_type

    def test_files_outside_the_allowlist_are_not_served(self):
        status, _, _ = _request("/notes.txt")
        assert status == 404

    @pytest.mark.parametrize(
        "path",
        [
            "/../config.json",
            "/js/../../config.json",
            "/%2e%2e/config.json",
            "/js/%2e%2e/%2e%2e/config.json",
            "/..%2fconfig.json",
        ],
    )
    def test_traversal_attempts_get_404(self, path):
        status, _, body = _request(path)
        assert status == 404
        assert b"coordinates" not in body

    def test_api_now_returns_json(self):
        status, headers, body = _request("/api/now")
        assert status == 200
        assert headers["Content-Type"] == "application/json"
        assert json.loads(body) == {"sun": None}

    def test_api_now_is_503_without_the_service(self):
        ScreenshotHandler.web_service = None
        status, _, _ = _request("/api/now")
        assert status == 503

    def test_api_now_is_500_when_building_fails(self):
        ScreenshotHandler.web_service.build_now.side_effect = RuntimeError("boom")
        status, _, body = _request("/api/now")
        assert status == 500
        assert b"boom" not in body

    def test_root_is_503_when_the_page_files_failed_to_load(self):
        ScreenshotHandler.static_site = None
        status, _, _ = _request("/")
        assert status == 503

    def test_unknown_api_path_is_404(self):
        status, _, _ = _request("/api/nope")
        assert status == 404

    def test_page_files_skip_the_rate_limit_but_the_api_does_not(self):
        ScreenshotHandler.rate_limiter = RateLimiter(rate_per_second=1)
        for _ in range(5):
            assert _request("/style.css")[0] == 200
        assert _request("/api/now")[0] == 200
        assert _request("/api/now")[0] == 429

    @staticmethod
    def _login(user, password):
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def test_wrong_password_on_a_page_file_is_still_rate_limited(self):
        ScreenshotHandler.auth_credentials = ("peter", "right")
        ScreenshotHandler.rate_limiter = RateLimiter(rate_per_second=1)
        wrong = self._login("peter", "wrong")
        assert _request("/style.css", wrong)[0] == 401
        assert _request("/style.css", wrong)[0] == 429
        assert _request("/", wrong)[0] == 429

    def test_rate_limit_does_not_reveal_a_right_password(self):
        # With a login configured, page files count against the limit whatever
        # credentials they carry. Otherwise 200-versus-429 would answer every
        # password guess even after the limit is used up.
        ScreenshotHandler.auth_credentials = ("peter", "right")
        ScreenshotHandler.rate_limiter = RateLimiter(rate_per_second=1)
        right = self._login("peter", "right")
        assert _request("/style.css", right)[0] == 200
        assert _request("/style.css", right)[0] == 429

    def test_existing_endpoints_still_work_alongside_the_page(self):
        status, _, body = _request("/health")
        assert status == 200
        assert body == b"OK"

    def test_missing_index_html_stops_the_site_loading(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            StaticSite(tmp_path / "empty")

    def test_create_server_hands_over_the_web_page(self):
        config = MagicMock(enabled=True, port=0, bind_address="127.0.0.1")
        config.rate_limit_per_second = 10
        service, site = MagicMock(), MagicMock()
        server = create_server(config, MagicMock(), service, site)
        try:
            assert ScreenshotHandler.web_service is service
            assert ScreenshotHandler.static_site is site
        finally:
            server.server_close()


class TestChartsRoute:
    """GET /api/charts: the curves behind the web page's chart views."""

    @pytest.fixture(autouse=True)
    def web_handler(self):
        ScreenshotHandler.clock_instance = MagicMock()
        ScreenshotHandler.rate_limiter = None
        ScreenshotHandler.auth_credentials = None
        ScreenshotHandler.static_site = None
        ScreenshotHandler.web_service = MagicMock()
        ScreenshotHandler.web_service.build_charts.return_value = {"date": "2026-10-08"}
        yield
        ScreenshotHandler.web_service = None

    def test_api_charts_returns_json(self):
        status, headers, body = _request("/api/charts")
        assert status == 200
        assert headers["Content-Type"] == "application/json"
        assert json.loads(body) == {"date": "2026-10-08"}

    def test_api_charts_ignores_a_query_string(self):
        assert _request("/api/charts?v=2")[0] == 200

    def test_api_charts_reads_nothing_else(self):
        _request("/api/charts")
        ScreenshotHandler.web_service.build_now.assert_not_called()
        assert ScreenshotHandler.clock_instance.mock_calls == []

    def test_api_charts_is_503_without_the_service(self):
        ScreenshotHandler.web_service = None
        assert _request("/api/charts")[0] == 503

    def test_api_charts_is_500_when_building_fails(self):
        ScreenshotHandler.web_service.build_charts.side_effect = RuntimeError("boom")
        status, _, body = _request("/api/charts")
        assert status == 500
        assert b"boom" not in body

    def test_api_charts_is_rate_limited(self):
        ScreenshotHandler.rate_limiter = RateLimiter(rate_per_second=1)
        assert _request("/api/charts")[0] == 200
        assert _request("/api/charts")[0] == 429
