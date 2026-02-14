"""Base view class and view manager for Solar Smart Clock."""

import logging
import threading
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Union

from PIL import Image, ImageDraw, ImageFont

from .colors import DARK_BLUE, LIGHT_BLUE, ORANGE, PURPLE, WHITE
from .font_manager import get_font_manager
from .renderers import NavBarRenderer
from .theme import Theme, get_theme

if TYPE_CHECKING:
    from ..config import Config
    from ..data import WeatherProvider, SolarProvider, LunarProvider

logger = logging.getLogger(__name__)


# Layout constants
HEADER_HEIGHT = 35
CONTENT_START_Y = 45
ROW_HEIGHT = 50
SECTION_PADDING = 10
FOOTER_HEIGHT = 25


class Spacing:
    """Standard spacing for consistent layouts."""

    TINY = 3
    SMALL = 5
    MEDIUM = 10
    LARGE = 20
    XLARGE = 35

    MARGIN_SMALL = 10
    MARGIN_MEDIUM = 20

    ROW_SPACING = 18
    SECTION_GAP = 22
    COLUMN_GAP = 10


class Layout:
    """Standard layout positions."""

    HEADER_HEIGHT = 35
    CONTENT_START = 45

    # Common row positions from top
    ROW_1 = 45
    ROW_2 = 85
    ROW_3 = 145
    ROW_4 = 230

    # Panel sizes
    INFO_BOX_HEIGHT = 55
    ROUNDED_RADIUS = 6


# Update interval constants (seconds)
UPDATE_REALTIME = 1  # Clock displays that update every second
UPDATE_FREQUENT = 60  # Weather, solar position
UPDATE_HOURLY = 3600  # Moon phase, analemma


# Typography scale constants
class FontSize:
    """Standard font sizes for consistent typography."""

    # Text sizes
    TITLE = 24
    SUBTITLE = 20
    BODY = 16
    SMALL = 14
    CAPTION = 12

    # Chart-specific sizes (minimum 12pt for readability)
    AXIS_LABEL = 12  # Chart axes (increased from 10pt)
    CHART_LABEL = 14  # Chart text

    # Value display sizes
    VALUE_LARGE = 48
    VALUE_MEDIUM = 36
    VALUE_SMALL = 24
    VALUE_TINY = 20  # Compact values


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

        # Get font manager singleton
        self._font_manager = get_font_manager()

    def get_font(self, size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """
        Get a font at the specified size.

        Uses DejaVu Sans as the default font, with fallbacks for different
        platforms. Falls back to PIL default if no system fonts available.

        Note: This now uses the global FontManager singleton for better
        memory efficiency and faster font access.

        Args:
            size: Font size in points

        Returns:
            PIL ImageFont
        """
        return self._font_manager.get_font(size)

    def get_bold_font(
        self, size: int
    ) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """
        Get a bold font at the specified size.

        Tries multiple font paths, falling back to regular font if bold unavailable.

        Note: This now uses the global FontManager singleton for better
        memory efficiency and faster font access.

        Args:
            size: Font size in points

        Returns:
            PIL ImageFont
        """
        return self._font_manager.get_bold_font(size)

    def get_theme(self) -> Theme:
        """
        Get the current theme.

        Returns:
            Current Theme instance from ThemeManager
        """
        return get_theme()

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
        theme = self.get_theme()
        font = self.get_font(font_size)
        bbox = draw.textbbox((0, 0), message, font=font)
        msg_width = bbox[2] - bbox[0]
        x = (self.width - msg_width) // 2
        y = self.content_height // 2
        draw.text((x, y), message, fill=theme.text_secondary, font=font)

    def render_header(
        self, draw: ImageDraw.ImageDraw, title: str, color: tuple[int, int, int]
    ) -> None:
        """
        Render a standard header bar with centered title.

        Args:
            draw: ImageDraw instance
            title: Title text to display
            color: Background color for header
        """
        # Draw header background
        draw.rectangle(((0, 0), (self.width, Layout.HEADER_HEIGHT)), fill=color)

        # Draw centered title
        font_title = self.get_bold_font(FontSize.TITLE)
        title_bbox = draw.textbbox((0, 0), title, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.width - title_width) // 2
        draw.text((title_x, 5), title, fill=WHITE, font=font_title)

    def render_text_centered(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        y: int,
        color: tuple[int, int, int],
        font_size: int,
    ) -> None:
        """
        Render horizontally centered text at a specific Y position.

        Args:
            draw: ImageDraw instance
            text: Text to display
            y: Y position for text
            color: Text color
            font_size: Font size to use
        """
        font = self.get_font(font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) // 2
        draw.text((x, y), text, fill=color, font=font)

    def render_info_box(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        label: str,
        value: str,
        label_color: Optional[tuple[int, int, int]] = None,
        value_color: Optional[tuple[int, int, int]] = None,
    ) -> None:
        """
        Render an info box with label and value.

        Args:
            draw: ImageDraw instance
            x: X position of box
            y: Y position of box
            width: Box width
            height: Box height
            label: Label text (smaller, above)
            value: Value text (larger, below)
            label_color: Color for label text (defaults to theme.text_secondary)
            value_color: Color for value text (defaults to theme.text_primary)
        """
        theme = self.get_theme()

        # Use theme defaults if colors not specified
        if label_color is None:
            label_color = theme.text_secondary
        if value_color is None:
            value_color = theme.text_primary

        # Draw box background
        draw.rounded_rectangle(
            ((x, y), (x + width, y + height)),
            radius=Layout.ROUNDED_RADIUS,
            fill=theme.background_panel,
        )

        # Draw label (centered, top portion)
        font_label = self.get_font(FontSize.SMALL)
        label_bbox = draw.textbbox((0, 0), label, font=font_label)
        label_width = label_bbox[2] - label_bbox[0]
        label_x = x + (width - label_width) // 2
        draw.text((label_x, y + 8), label, fill=label_color, font=font_label)

        # Draw value (centered, bottom portion)
        font_value = self.get_bold_font(FontSize.BODY)
        value_bbox = draw.textbbox((0, 0), value, font=font_value)
        value_width = value_bbox[2] - value_bbox[0]
        value_x = x + (width - value_width) // 2
        draw.text((value_x, y + 30), value, fill=value_color, font=font_value)

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
        theme = self.get_theme()

        # Create image with themed background
        image = Image.new("RGB", (self.width, self.height), theme.background)
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
        theme = self.get_theme()
        NavBarRenderer.render(
            draw=draw,
            width=self.width,
            height=self.height,
            nav_height=self.nav_height,
            current_index=current_index,
            total_views=total_views,
            button_color=theme.nav_button,
            dot_color_active=theme.nav_dot_active,
            dot_color_inactive=theme.nav_dot_inactive,
            background_color=theme.nav_background,
        )

    def get_time_header_color(self) -> tuple[int, int, int]:
        """
        Get header color based on current time of day.

        Uses solar provider data when available for accurate boundaries,
        falls back to fixed hour thresholds otherwise.

        Returns appropriate colors for different times:
        - Night (before dawn): Dark blue
        - Dawn/Sunrise and Sunset/Dusk: Orange
        - Day: Light blue
        - After dusk: Purple
        """
        import datetime

        now = datetime.datetime.now()

        if self.providers.solar is not None:
            sun_times = self.providers.solar.get_sun_times()
            if sun_times is not None:
                # Make now tz-aware if sun_times are tz-aware
                if sun_times.sunrise.tzinfo is not None:
                    now = datetime.datetime.now(sun_times.sunrise.tzinfo)

                if now < sun_times.dawn:
                    return DARK_BLUE
                elif now < sun_times.sunrise:
                    return ORANGE
                elif now < sun_times.sunset:
                    return LIGHT_BLUE
                elif now < sun_times.dusk:
                    return ORANGE
                else:
                    return PURPLE

        # Fallback: fixed hour thresholds
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
