"""Main entry point for Solar Smart Clock."""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from PIL import Image

from .config import Config, load_config, get_api_key
from .display import Display
from .http_server import create_server, start_server_thread
from .touch_handler import TouchHandler
from .data import WeatherProvider, SolarProvider, LunarProvider
from .views import VIEW_CLASSES, ViewManager
from .views.base import DataProviders

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


class SolarClock:
    """Main Solar Clock application."""

    def __init__(self, config: Config):
        """
        Initialize the Solar Clock application.

        Args:
            config: Application configuration
        """
        self.config = config
        self.running = False
        self._last_frame: Optional[Image.Image] = None

        # Initialize data providers
        api_key = get_api_key()
        self.providers = DataProviders(
            weather=(
                WeatherProvider(
                    api_key=api_key or "",
                    latitude=config.location.latitude,
                    longitude=config.location.longitude,
                    units=config.weather.units,
                    weather_interval=config.weather.update_interval_seconds,
                    aqi_interval=config.air_quality.update_interval_seconds,
                )
                if api_key
                else None
            ),
            solar=SolarProvider(
                name=config.location.name,
                region=config.location.region,
                timezone=config.location.timezone,
                latitude=config.location.latitude,
                longitude=config.location.longitude,
            ),
            lunar=LunarProvider(
                latitude=config.location.latitude,
                longitude=config.location.longitude,
            ),
        )

        # Initialize views
        views = [ViewClass(config, self.providers) for ViewClass in VIEW_CLASSES]
        self.view_manager = ViewManager(views, config.appearance.default_view)

        # Initialize display
        self.display = Display(config.display)

        # Initialize HTTP server
        self.http_server = create_server(config.http_server, self)
        self.http_thread = None

        # Initialize touch handler
        self.touch_handler = TouchHandler(
            config=config.touch,
            on_next=self.view_manager.next_view,
            on_prev=self.view_manager.prev_view,
            display_width=config.display.width,
            display_height=config.display.height,
            nav_bar_height=config.display.nav_bar_height,
        )

    def get_last_frame(self) -> Optional[Image.Image]:
        """Get the last rendered frame (for HTTP screenshots)."""
        return self._last_frame

    def run(self) -> None:
        """Run the main application loop."""
        logger.info("Starting Solar Clock...")

        # Open display
        if not self.display.open():
            logger.error("Failed to open display")
            return

        # Start HTTP server
        if self.http_server:
            self.http_thread = start_server_thread(self.http_server)
            logger.info(f"HTTP server running on port {self.config.http_server.port}")

        # Start touch handler
        self.touch_handler.start()

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.running = True
        logger.info("Solar Clock running. Press Ctrl+C to stop.")

        try:
            while self.running:
                # Render current view
                frame = self.view_manager.render_current()
                self._last_frame = frame

                # Write to display
                self.display.write_frame(frame)

                # Sleep until next update
                current_view = self.view_manager.get_current_view()
                self.view_manager.view_changed.wait(
                    timeout=current_view.update_interval
                )
                self.view_manager.view_changed.clear()

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self._cleanup()

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def _cleanup(self) -> None:
        """Clean up resources on shutdown."""
        logger.info("Cleaning up...")

        # Stop touch handler
        self.touch_handler.stop()

        # Stop HTTP server
        if self.http_server:
            self.http_server.shutdown()

        # Close display
        self.display.close()

        logger.info("Cleanup complete")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Solar Smart Clock - Multi-view solar clock display"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to config.json file",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--bind-all",
        action="store_true",
        help="Bind HTTP server to all interfaces (0.0.0.0) instead of localhost",
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        logger.error(f"Config file not found: {e}")
        logger.info("Create a config.json from config.example.json")
        return 1
    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        return 1

    # Override bind address if --bind-all specified
    if args.bind_all:
        config.http_server.bind_address = "0.0.0.0"
        logger.warning("HTTP server will bind to all interfaces (0.0.0.0)")

    # Check for API key
    if not get_api_key():
        logger.warning(
            "OPENWEATHER_API_KEY not set. Weather and air quality data will be unavailable."
        )

    # Run application
    clock = SolarClock(config)
    clock.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
