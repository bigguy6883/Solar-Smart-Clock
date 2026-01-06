"""Analemma view - figure-8 sun position diagram."""

import datetime
import math
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from .base import BaseView, WHITE, BLACK, YELLOW, ORANGE, GRAY, LIGHT_GRAY, GREEN, BLUE

if TYPE_CHECKING:
    from ..config import Config
    from .base import DataProviders


class AnalemmaView(BaseView):
    """Analemma view showing figure-8 sun position pattern."""

    name = "analemma"
    title = "Analemma"
    update_interval = 3600

    # Season colors
    SPRING_COLOR = GREEN
    SUMMER_COLOR = YELLOW
    FALL_COLOR = ORANGE
    WINTER_COLOR = BLUE

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the analemma view content."""
        # Header
        draw.rectangle([(0, 0), (self.width, 35)], fill=ORANGE)
        font_title = self.get_bold_font(24)
        title_bbox = draw.textbbox((0, 0), "Analemma", font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(
            ((self.width - title_width) // 2, 5),
            "Analemma",
            fill=WHITE,
            font=font_title,
        )

        # Analemma diagram (left side)
        self._render_analemma_diagram(draw, 45)

        # Info panel (right side)
        self._render_info_panel(draw, 45)

    def _render_analemma_diagram(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render the figure-8 analemma pattern."""
        # Diagram area
        center_x = 120
        center_y = y + 100
        scale_x = 60  # Horizontal scale (equation of time)
        scale_y = 80  # Vertical scale (elevation)

        font_tiny = self.get_font(10)

        # Axis labels
        draw.text((center_x - 15, y), "Summer", fill=YELLOW, font=font_tiny)
        draw.text((center_x - 15, y + 195), "winter", fill=BLUE, font=font_tiny)
        draw.text((5, center_y - 5), "Sun", fill=GRAY, font=font_tiny)
        draw.text((5, center_y + 8), "early", fill=GRAY, font=font_tiny)
        draw.text((200, center_y - 5), "Sun", fill=GRAY, font=font_tiny)
        draw.text((200, center_y + 8), "late", fill=GRAY, font=font_tiny)

        # Draw axis lines
        draw.line([(center_x, y + 20), (center_x, y + 190)], fill=GRAY, width=1)
        draw.line([(30, center_y), (210, center_y)], fill=GRAY, width=1)

        if self.providers.lunar is None or not self.providers.lunar.available:
            draw.text((60, center_y), "Data unavailable", fill=GRAY, font=self.get_font(14))
            return

        # Get analemma data points
        points = self.providers.lunar.get_analemma_data()
        if not points:
            return

        # Draw the figure-8 with seasonal colors
        today = datetime.date.today()
        today_point = None

        for i, point in enumerate(points):
            # Map equation of time (-15 to +15 min) to x
            x = center_x + int((point.equation_of_time / 15) * scale_x)

            # Map elevation to y
            elev_normalized = (point.elevation - 30) / 50  # Normalize around 30-80 degrees
            y_pos = center_y - int(elev_normalized * scale_y)

            # Determine season color
            month = point.date.month
            if 3 <= month <= 5:
                color = self.SPRING_COLOR
            elif 6 <= month <= 8:
                color = self.SUMMER_COLOR
            elif 9 <= month <= 11:
                color = self.FALL_COLOR
            else:
                color = self.WINTER_COLOR

            # Draw point
            draw.ellipse([(x - 2, y_pos - 2), (x + 2, y_pos + 2)], fill=color)

            # Check if this is close to today
            days_diff = abs((point.date - today).days)
            if days_diff < 7:
                today_point = (x, y_pos)

        # Highlight today's position
        if today_point:
            x, y_pos = today_point
            draw.ellipse([(x - 6, y_pos - 6), (x + 6, y_pos + 6)], fill=WHITE, outline=YELLOW)

    def _render_info_panel(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render the info panel on the right side."""
        font = self.get_font(14)
        font_large = self.get_bold_font(24)
        font_small = self.get_font(12)

        x = 250

        # Today box
        draw.rectangle([(x, y), (self.width - 10, y + 90)], fill=(30, 30, 30), outline=GRAY)
        draw.text((x + 10, y + 5), "Today", fill=WHITE, font=self.get_bold_font(16))

        if self.providers.lunar:
            eot = self.providers.lunar.get_equation_of_time()
            if eot:
                sign = "early" if eot > 0 else "late"
                draw.text((x + 10, y + 25), "Sun is", fill=GRAY, font=font)
                draw.text((x + 10, y + 42), f"{abs(eot):.1f} min", fill=YELLOW, font=font_large)
                draw.text((x + 10, y + 70), sign, fill=LIGHT_GRAY, font=font)

        # Sun path info
        draw.rectangle([(x, y + 100), (self.width - 10, y + 175)], fill=(30, 30, 30), outline=GRAY)
        draw.text((x + 10, y + 105), "Sun path", fill=WHITE, font=self.get_bold_font(16))

        if self.providers.solar:
            pos = self.providers.solar.get_solar_position()
            if pos:
                height = "high" if pos.elevation > 45 else "low"
                draw.text((x + 10, y + 130), height, fill=YELLOW, font=font_large)
                draw.text((x + 10, y + 155), f"{pos.elevation:.1f}° S", fill=LIGHT_GRAY, font=font)

        # Season legend
        draw.text((x, y + 185), "Legend:", fill=GRAY, font=font_small)
        legend_items = [
            ("Sp", self.SPRING_COLOR),
            ("Su", self.SUMMER_COLOR),
            ("Fa", self.FALL_COLOR),
            ("Wi", self.WINTER_COLOR),
        ]
        legend_x = x + 50
        for label, color in legend_items:
            draw.ellipse([(legend_x, y + 188), (legend_x + 8, y + 196)], fill=color)
            draw.text((legend_x + 12, y + 185), label, fill=LIGHT_GRAY, font=font_small)
            legend_x += 40
