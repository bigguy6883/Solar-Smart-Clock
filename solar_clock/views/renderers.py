"""Renderer classes for common UI components."""

from typing import Tuple

from PIL import ImageDraw

from .colors import WHITE, GRAY
from .font_manager import get_font_manager


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
