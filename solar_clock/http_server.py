"""HTTP server for screenshots and view navigation with security features."""

import base64
import json
import logging
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .config import HttpServerConfig

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(self, rate_per_second: int = 10):
        self.rate = rate_per_second
        self.tokens: float = float(rate_per_second)
        self.last_update = time.time()
        self.lock = threading.Lock()

    def allow(self) -> bool:
        """Check if request is allowed. Returns True if allowed."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


class ScreenshotHandler(BaseHTTPRequestHandler):
    """HTTP request handler for screenshots and navigation.

    Note: clock_instance, rate_limiter, and auth_credentials are stored as
    class variables (required by BaseHTTPRequestHandler's design). This means
    only one server configuration can exist at a time.
    """

    # Class-level references (set by create_server)
    clock_instance = None
    rate_limiter: Optional[RateLimiter] = None
    auth_credentials: Optional[tuple[str, str]] = None  # (user, pass)

    def log_message(self, format: str, *args) -> None:
        """Override to use proper logging."""
        logger.debug(f"{self.client_address[0]} - {format % args}")

    def _check_auth(self) -> bool:
        """Check basic auth if configured. Returns True if allowed."""
        if self.auth_credentials is None:
            return True

        auth_header = self.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return False

        try:
            encoded = auth_header[6:]  # Remove "Basic "
            decoded = base64.b64decode(encoded).decode("utf-8")
            user, password = decoded.split(":", 1)
            return (user, password) == self.auth_credentials
        except (ValueError, UnicodeDecodeError):
            return False

    def _send_unauthorized(self) -> None:
        """Send 401 Unauthorized response."""
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Solar Clock"')
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Unauthorized")

    def _send_rate_limited(self) -> None:
        """Send 429 Too Many Requests response."""
        self.send_response(429)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Retry-After", "1")
        self.end_headers()
        self.wfile.write(b"Too Many Requests")

    def _send_text(self, status: int, text: str) -> None:
        """Send a text response."""
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def _send_json(self, status: int, data: dict) -> None:
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _send_png(self, image_data: bytes) -> None:
        """Send a PNG image response."""
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(image_data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(image_data)

    def _require_clock(self) -> bool:
        """Check that clock_instance is available. Sends 503 if not.

        Returns:
            True if clock_instance is available, False otherwise.
        """
        if self.clock_instance is None:
            self._send_text(503, "Clock not initialized")
            return False
        return True

    def _send_view_status(self) -> None:
        """Send current view name and index as text response.

        Must only be called after _require_clock() returns True.
        """
        clock = self.clock_instance
        assert clock is not None
        view = clock.view_manager.get_current()
        index = clock.view_manager.get_index()
        count = clock.view_manager.get_count()
        self._send_text(200, f"{view} ({index + 1}/{count})")

    def do_GET(self) -> None:
        """Handle GET requests."""
        # Rate limiting
        if self.rate_limiter and not self.rate_limiter.allow():
            self._send_rate_limited()
            return

        # Authentication
        if not self._check_auth():
            self._send_unauthorized()
            return

        path = self.path.lower()

        if path == "/health":
            self._send_text(200, "OK")

        elif path == "/screenshot":
            if not self._require_clock():
                return
            clock = self.clock_instance
            assert clock is not None
            try:
                frame = clock.view_manager.render_current()
                if frame is None:
                    frame = clock.get_last_frame()
                if frame is None:
                    self._send_text(503, "No frame available")
                    return
                buffer = BytesIO()
                frame.save(buffer, format="PNG")
                self._send_png(buffer.getvalue())
            except Exception as e:
                logger.error(f"Screenshot error: {e}")
                self._send_text(500, f"Error: {e}")

        elif path == "/next":
            if not self._require_clock():
                return
            clock = self.clock_instance
            assert clock is not None
            clock.view_manager.next_view()
            self._send_view_status()

        elif path == "/prev":
            if not self._require_clock():
                return
            clock = self.clock_instance
            assert clock is not None
            clock.view_manager.prev_view()
            self._send_view_status()

        elif path == "/view":
            if not self._require_clock():
                return
            self._send_view_status()

        elif path == "/theme":
            if not self._require_clock():
                return
            clock = self.clock_instance
            assert clock is not None
            self._send_json(200, clock.theme_manager.get_status())

        elif path.startswith("/theme/"):
            if not self._require_clock():
                return
            clock = self.clock_instance
            assert clock is not None
            mode = path.split("/")[-1]
            if mode in ("auto", "day", "night"):
                clock.theme_manager.set_mode(mode)
                self._send_json(200, clock.theme_manager.get_status())
            else:
                self._send_text(404, "Not Found")

        elif path == "/theme":
            if self.clock_instance is None:
                self._send_text(503, "Clock not initialized")
                return

            status = self.clock_instance.theme_manager.get_status()
            self._send_json(200, status)

        elif path == "/theme/auto":
            if self.clock_instance is None:
                self._send_text(503, "Clock not initialized")
                return

            self.clock_instance.theme_manager.set_mode("auto")
            status = self.clock_instance.theme_manager.get_status()
            self._send_json(200, status)

        elif path == "/theme/day":
            if self.clock_instance is None:
                self._send_text(503, "Clock not initialized")
                return

            self.clock_instance.theme_manager.set_mode("day")
            status = self.clock_instance.theme_manager.get_status()
            self._send_json(200, status)

        elif path == "/theme/night":
            if self.clock_instance is None:
                self._send_text(503, "Clock not initialized")
                return

            self.clock_instance.theme_manager.set_mode("night")
            status = self.clock_instance.theme_manager.get_status()
            self._send_json(200, status)

        else:
            self._send_text(404, "Not Found")


def create_server(
    config: "HttpServerConfig",
    clock_instance,
) -> Optional[HTTPServer]:
    """
    Create and configure the HTTP server.

    Args:
        config: HTTP server configuration
        clock_instance: Reference to main clock instance

    Returns:
        Configured HTTPServer, or None if disabled
    """
    if not config.enabled:
        logger.info("HTTP server disabled in config")
        return None

    # Set up handler class attributes
    ScreenshotHandler.clock_instance = clock_instance
    ScreenshotHandler.rate_limiter = RateLimiter(config.rate_limit_per_second)

    # Check for auth credentials in environment
    auth_user = os.environ.get("HTTP_AUTH_USER")
    auth_pass = os.environ.get("HTTP_AUTH_PASS")
    if auth_user and auth_pass:
        ScreenshotHandler.auth_credentials = (auth_user, auth_pass)
        logger.info("HTTP Basic Auth enabled")
    else:
        ScreenshotHandler.auth_credentials = None

    # Create server
    bind_address = (config.bind_address, config.port)
    server = HTTPServer(bind_address, ScreenshotHandler)

    logger.info(f"HTTP server configured on {config.bind_address}:{config.port}")

    if config.bind_address == "0.0.0.0":
        logger.warning(
            "HTTP server bound to all interfaces (0.0.0.0). "
            "Consider using 127.0.0.1 for local-only access."
        )

    return server


def start_server_thread(server: HTTPServer) -> threading.Thread:
    """
    Start the HTTP server in a daemon thread.

    Args:
        server: HTTPServer instance to run

    Returns:
        The daemon thread running the server
    """
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("HTTP server thread started")
    return thread
