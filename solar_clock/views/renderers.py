"""Renderer classes for common UI components."""

from typing import Tuple

from PIL import ImageDraw

from .colors import WHITE, GRAY, LIGHT_GRAY, DARK_GRAY
from .font_manager import get_font_manager


class HeaderRenderer:
    """Renders standardized headers for views."""

    @staticmethod
    def render(
        draw: ImageDraw.ImageDraw,
        width: int,
        title: str,
        color: Tuple[int, int, int],
        height: int = 35,
        title_size: int = 24,
    ) -> None:
        """
        Render a standard header bar with centered title.

        Args:
            draw: ImageDraw instance
            width: Width of the header
            title: Title text to display
            color: Background color for header
            height: Height of header bar (default 35)
            title_size: Font size for title (default 24)
        """
        font_manager = get_font_manager()

        # Draw header background
        draw.rectangle(((0, 0), (width, height)), fill=color)

        # Draw centered title
        font_title = font_manager.get_bold_font(title_size)
        title_bbox = draw.textbbox((0, 0), title, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        draw.text((title_x, 5), title, fill=WHITE, font=font_title)


class PanelRenderer:
    """Renders info panels with labels and values."""

    @staticmethod
    def render(
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        label: str,
        value: str,
        label_color: Tuple[int, int, int] = LIGHT_GRAY,
        value_color: Tuple[int, int, int] = WHITE,
        background_color: Tuple[int, int, int] = DARK_GRAY,
        radius: int = 6,
        label_size: int = 14,
        value_size: int = 16,
    ) -> None:
        """
        Render an info panel with label and value.

        Args:
            draw: ImageDraw instance
            x: X position of panel
            y: Y position of panel
            width: Panel width
            height: Panel height
            label: Label text (smaller, above)
            value: Value text (larger, below)
            label_color: Color for label text
            value_color: Color for value text
            background_color: Background color for panel
            radius: Corner radius for rounded rectangle
            label_size: Font size for label
            value_size: Font size for value (bold)
        """
        font_manager = get_font_manager()

        # Draw panel background
        draw.rounded_rectangle(
            ((x, y), (x + width, y + height)), radius=radius, fill=background_color
        )

        # Draw label (centered, top portion)
        font_label = font_manager.get_font(label_size)
        label_bbox = draw.textbbox((0, 0), label, font=font_label)
        label_width = label_bbox[2] - label_bbox[0]
        label_x = x + (width - label_width) // 2
        draw.text((label_x, y + 8), label, fill=label_color, font=font_label)

        # Draw value (centered, bottom portion)
        font_value = font_manager.get_bold_font(value_size)
        value_bbox = draw.textbbox((0, 0), value, font=font_value)
        value_width = value_bbox[2] - value_bbox[0]
        value_x = x + (width - value_width) // 2
        draw.text((value_x, y + 30), value, fill=value_color, font=font_value)


class NavBarRenderer:
    """Renders navigation bars with buttons and page indicators."""

    @staticmethod
    def render(
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        nav_height: int,
        current_index: int,
        total_views: int,
        button_color: Tuple[int, int, int] = (60, 60, 60),
        dot_color_active: Tuple[int, int, int] = WHITE,
        dot_color_inactive: Tuple[int, int, int] = GRAY,
        background_color: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """
        Render the bottom navigation bar with buttons and page indicators.

        Args:
            draw: ImageDraw instance
            width: Total width
            height: Total height
            nav_height: Height of navigation bar
            current_index: Current view index (0-based)
            total_views: Total number of views
            button_color: Color for navigation buttons
            dot_color_active: Color for active page indicator
            dot_color_inactive: Color for inactive page indicators
            background_color: Background color for nav bar
        """
        font_manager = get_font_manager()
        nav_top = height - nav_height

        # Background
        draw.rectangle(((0, nav_top), (width, height)), fill=background_color)

        # Prev button (<)
        button_width = 50
        button_height = 30
        button_y = nav_top + (nav_height - button_height) // 2

        draw.rectangle(
            ((10, button_y), (10 + button_width, button_y + button_height)),
            fill=button_color,
            outline=GRAY,
        )
        font = font_manager.get_font(20)
        draw.text((28, button_y + 2), "<", fill=WHITE, font=font)

        # Next button (>)
        draw.rectangle(
            (
                (width - 10 - button_width, button_y),
                (width - 10, button_y + button_height),
            ),
            fill=button_color,
            outline=GRAY,
        )
        draw.text((width - 32, button_y + 2), ">", fill=WHITE, font=font)

        # Page indicator dots
        dot_radius = 4
        # Dynamic spacing scales down if more views are added
        dot_spacing = min(14, (width - 100) // total_views)
        total_width = (total_views - 1) * dot_spacing
        start_x = (width - total_width) // 2
        dot_y = nav_top + nav_height // 2

        for i in range(total_views):
            x = start_x + i * dot_spacing
            color = dot_color_active if i == current_index else dot_color_inactive
            draw.ellipse(
                [
                    (x - dot_radius, dot_y - dot_radius),
                    (x + dot_radius, dot_y + dot_radius),
                ],
                fill=color,
            )
