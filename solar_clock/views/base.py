"""Base view class and view manager for Solar Smart Clock."""

import logging
import threading
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Union

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from ..config import Config
    from ..data import WeatherProvider, SolarProvider, LunarProvider

logger = logging.getLogger(__name__)


# Common colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 220, 50)
ORANGE = (255, 140, 0)
BLUE = (100, 149, 237)
DARK_BLUE = (25, 25, 112)
LIGHT_BLUE = (135, 206, 235)
GRAY = (128, 128, 128)
LIGHT_GRAY = (180, 180, 180)
DARK_GRAY = (50, 50, 50)
RED = (255, 80, 80)
PURPLE = (147, 112, 219)
GREEN = (0, 200, 0)
MOON_YELLOW = (255, 248, 220)

# AQI colors
AQI_GOOD = (0, 228, 0)
AQI_MODERATE = (255, 255, 0)
AQI_UNHEALTHY_SENSITIVE = (255, 126, 0)
AQI_UNHEALTHY = (255, 0, 0)
AQI_VERY_UNHEALTHY = (143, 63, 151)
AQI_HAZARDOUS = (126, 0, 35)

# Navigation bar colors
NAV_BUTTON_COLOR = (60, 60, 60)
NAV_BUTTON_ACTIVE = (80, 80, 80)

# Layout constants
HEADER_HEIGHT = 35
CONTENT_START_Y = 45
ROW_HEIGHT = 50
SECTION_PADDING = 10
FOOTER_HEIGHT = 25

# Update interval constants (seconds)
UPDATE_REALTIME = 1  # Clock displays that update every second
UPDATE_FREQUENT = 60  # Weather, solar position
UPDATE_HOURLY = 3600  # Moon phase, analemma

# Font paths (in order of preference)
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Debian/Ubuntu/Raspbian
    "/usr/share/fonts/TTF/DejaVuSans.ttf",  # Arch Linux
    "/System/Library/Fonts/Helvetica.ttc",  # macOS
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",  # Alternative Linux path
]

BOLD_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Debian/Ubuntu/Raspbian
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",  # Arch Linux
    "/System/Library/Fonts/Helvetica.ttc",  # macOS (bold variant)
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",  # Alternative Linux path
]


# Typography scale constants
class FontSize:
    """Standard font sizes for consistent typography."""

    # Text sizes
    TITLE = 24
    SUBTITLE = 20
    BODY = 16
    SMALL = 14
    CAPTION = 12

    # Value display sizes
    VALUE_LARGE = 48
    VALUE_MEDIUM = 36
    VALUE_SMALL = 24


class DataProviders:
    """Container for data provider instances."""

    def __init__(
        self,
        weather: Optional["WeatherProvider"] = None,
        solar: Optional["SolarProvider"] = None,
        lunar: Optional["LunarProvider"] = None,
    ):
        self.weather = weather
        self.solar = solar
        self.lunar = lunar


class BaseView(ABC):
    """
    Abstract base class for all views.

    Each view renders to a PIL Image and is responsible for its own
    layout and data fetching.
    """

    # View metadata (override in subclasses)
    name: str = "base"
    title: str = "Base View"
    update_interval: int = 1  # Seconds between updates

    def __init__(
        self,
        config: "Config",
        providers: DataProviders,
    ):
        """
        Initialize view.

        Args:
            config: Application configuration
            providers: Data provider instances
        """
        self.config = config
        self.providers = providers
        self.width = config.display.width
        self.height = config.display.height
        self.nav_height = config.display.nav_bar_height
        self.content_height = self.height - self.nav_height

        # Font cache
        self._fonts: dict[int, Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]] = {}
        self._bold_fonts: dict[
            int, Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]
        ] = {}

    def get_font(self, size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """
        Get a font at the specified size.

        Uses DejaVu Sans as the default font, with fallbacks for different
        platforms. Falls back to PIL default if no system fonts available.

        Args:
            size: Font size in points

        Returns:
            PIL ImageFont
        """
        if size not in self._fonts:
            for path in FONT_PATHS:
                try:
                    self._fonts[size] = ImageFont.truetype(path, size)
                    break
                except OSError:
                    continue
            else:
                # No fonts found, use PIL default
                self._fonts[size] = ImageFont.load_default()
        return self._fonts[size]

    def get_bold_font(
        self, size: int
    ) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """
        Get a bold font at the specified size.

        Tries multiple font paths, falling back to regular font if bold unavailable.
        """
        if size not in self._bold_fonts:
            for path in BOLD_FONT_PATHS:
                try:
                    self._bold_fonts[size] = ImageFont.truetype(path, size)
                    break
                except OSError:
                    continue
            else:
                # No bold fonts found, fall back to regular font
                self._bold_fonts[size] = self.get_font(size)
        return self._bold_fonts[size]

    def render_centered_message(
        self, draw: ImageDraw.ImageDraw, message: str, font_size: int = 18
    ) -> None:
        """
        Render a centered message (typically for error/no-data states).

        Args:
            draw: ImageDraw instance
            message: Message to display
            font_size: Font size to use (default 18)
        """
        font = self.get_font(font_size)
        bbox = draw.textbbox((0, 0), message, font=font)
        msg_width = bbox[2] - bbox[0]
        x = (self.width - msg_width) // 2
        y = self.content_height // 2
        draw.text((x, y), message, fill=LIGHT_GRAY, font=font)

    @abstractmethod
    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """
        Render the view content.

        This method should draw the main view content, excluding the
        navigation bar which is drawn by the base class.

        Args:
            draw: ImageDraw instance for the image
            image: The PIL Image being rendered to
        """
        pass

    def render(self, current_index: int, total_views: int) -> Image.Image:
        """
        Render the complete view including navigation bar.

        Args:
            current_index: Current view index (0-based)
            total_views: Total number of views

        Returns:
            PIL Image ready for display
        """
        # Create image
        image = Image.new("RGB", (self.width, self.height), BLACK)
        draw = ImageDraw.Draw(image)

        # Render view-specific content
        self.render_content(draw, image)

        # Render navigation bar
        self._render_nav_bar(draw, current_index, total_views)

        return image

    def _render_nav_bar(
        self, draw: ImageDraw.ImageDraw, current_index: int, total_views: int
    ) -> None:
        """Render the bottom navigation bar with buttons and page indicators."""
        nav_top = self.height - self.nav_height

        # Background
        draw.rectangle(((0, nav_top), (self.width, self.height)), fill=BLACK)

        # Prev button (<)
        button_width = 50
        button_height = 30
        button_y = nav_top + (self.nav_height - button_height) // 2

        draw.rectangle(
            ((10, button_y), (10 + button_width, button_y + button_height)),
            fill=NAV_BUTTON_COLOR,
            outline=GRAY,
        )
        font = self.get_font(20)
        draw.text((28, button_y + 2), "<", fill=WHITE, font=font)

        # Next button (>)
        draw.rectangle(
            (
                (self.width - 10 - button_width, button_y),
                (self.width - 10, button_y + button_height),
            ),
            fill=NAV_BUTTON_COLOR,
            outline=GRAY,
        )
        draw.text((self.width - 32, button_y + 2), ">", fill=WHITE, font=font)

        # Page indicator dots
        dot_radius = 4
        # Dynamic spacing scales down if more views are added
        dot_spacing = min(14, (self.width - 100) // total_views)
        total_width = (total_views - 1) * dot_spacing
        start_x = (self.width - total_width) // 2
        dot_y = nav_top + self.nav_height // 2

        for i in range(total_views):
            x = start_x + i * dot_spacing
            color = WHITE if i == current_index else GRAY
            draw.ellipse(
                [
                    (x - dot_radius, dot_y - dot_radius),
                    (x + dot_radius, dot_y + dot_radius),
                ],
                fill=color,
            )

    def get_time_header_color(self) -> tuple[int, int, int]:
        """
        Get header color based on current time of day.

        Returns appropriate colors for different times:
        - Night (before dawn): Dark blue
        - Dawn/Dusk: Orange
        - Day: Light blue
        - Evening: Purple
        """
        import datetime

        now = datetime.datetime.now()
        hour = now.hour

        if hour < 6:
            return DARK_BLUE
        elif hour < 8:
            return ORANGE
        elif hour < 17:
            return LIGHT_BLUE
        elif hour < 20:
            return ORANGE
        else:
            return PURPLE


class ViewManager:
    """Manages navigation between views."""

    def __init__(self, views: list[BaseView], default_index: int = 0):
        """
        Initialize view manager.

        Args:
            views: List of view instances
            default_index: Starting view index
        """
        self.views = views
        self.current_index = default_index
        self.view_changed = threading.Event()

    def next_view(self) -> None:
        """Navigate to next view."""
        self.current_index = (self.current_index + 1) % len(self.views)
        self.view_changed.set()

    def prev_view(self) -> None:
        """Navigate to previous view."""
        self.current_index = (self.current_index - 1) % len(self.views)
        self.view_changed.set()

    def get_current(self) -> str:
        """Get current view name."""
        return self.views[self.current_index].name

    def get_index(self) -> int:
        """Get current view index."""
        return self.current_index

    def get_count(self) -> int:
        """Get total number of views."""
        return len(self.views)

    def get_current_view(self) -> BaseView:
        """Get current view instance."""
        return self.views[self.current_index]

    def render_current(self) -> Image.Image:
        """Render the current view."""
        view = self.views[self.current_index]
        return view.render(self.current_index, len(self.views))
