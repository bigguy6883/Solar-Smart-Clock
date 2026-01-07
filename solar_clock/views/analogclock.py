"""Analog clock view - traditional clock face."""

import datetime
import math
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from .base import (
    BaseView,
    WHITE,
    BLACK,
    GRAY,
    LIGHT_GRAY,
    DARK_BLUE,
    LIGHT_BLUE,
    ORANGE,
)

if TYPE_CHECKING:
    from ..config import Config
    from .base import DataProviders


class AnalogClockView(BaseView):
    """Traditional analog clock face view."""

    name = "analogclock"
    title = "Analog Clock"
    update_interval = 1

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the analog clock view content."""
        now = datetime.datetime.now()
        header_color = self.get_time_header_color()

        # Background based on time of day
        draw.rectangle([(0, 0), (self.width, self.content_height)], fill=header_color)

        # Clock face
        self._render_clock_face(draw, image, now)

        # Date below clock
        font_date = self.get_font(18)
        date_str = now.strftime("%A, %B %d")
        date_bbox = draw.textbbox((0, 0), date_str, font=font_date)
        date_width = date_bbox[2] - date_bbox[0]
        draw.text(
            ((self.width - date_width) // 2, self.content_height - 35),
            date_str,
            fill=WHITE,
            font=font_date,
        )

    def _render_clock_face(
        self, draw: ImageDraw.ImageDraw, image: Image.Image, now: datetime.datetime
    ) -> None:
        """Render the clock face with hands."""
        center_x = self.width // 2
        center_y = (self.content_height - 40) // 2 + 10
        radius = 100

        # Clock face background
        draw.ellipse(
            [
                (center_x - radius - 5, center_y - radius - 5),
                (center_x + radius + 5, center_y + radius + 5),
            ],
            fill=(240, 240, 230),
            outline=GRAY,
            width=3,
        )

        # Hour markers
        for hour in range(12):
            angle = math.radians(hour * 30 - 90)  # 30 degrees per hour, offset by -90

            # Marker position
            inner_r = radius - 15
            outer_r = radius - 5
            x1 = center_x + int(inner_r * math.cos(angle))
            y1 = center_y + int(inner_r * math.sin(angle))
            x2 = center_x + int(outer_r * math.cos(angle))
            y2 = center_y + int(outer_r * math.sin(angle))

            # Draw marker (thicker for 12, 3, 6, 9)
            width = 3 if hour % 3 == 0 else 1
            draw.line([(x1, y1), (x2, y2)], fill=(50, 50, 50), width=width)

            # Hour number dots for other hours
            if hour % 3 != 0:
                dot_r = radius - 10
                dx = center_x + int(dot_r * math.cos(angle))
                dy = center_y + int(dot_r * math.sin(angle))
                draw.ellipse([(dx - 2, dy - 2), (dx + 2, dy + 2)], fill=(50, 50, 50))

        # Minute markers
        for minute in range(60):
            if minute % 5 == 0:
                continue  # Skip hour markers
            angle = math.radians(minute * 6 - 90)
            inner_r = radius - 8
            outer_r = radius - 3
            x1 = center_x + int(inner_r * math.cos(angle))
            y1 = center_y + int(inner_r * math.sin(angle))
            x2 = center_x + int(outer_r * math.cos(angle))
            y2 = center_y + int(outer_r * math.sin(angle))
            draw.line([(x1, y1), (x2, y2)], fill=(100, 100, 100), width=1)

        # Hour hand
        hour = now.hour % 12
        minute = now.minute
        hour_angle = math.radians((hour + minute / 60) * 30 - 90)
        hour_length = radius * 0.5
        hour_x = center_x + int(hour_length * math.cos(hour_angle))
        hour_y = center_y + int(hour_length * math.sin(hour_angle))
        draw.line([(center_x, center_y), (hour_x, hour_y)], fill=BLACK, width=6)

        # Minute hand
        minute_angle = math.radians(minute * 6 - 90)
        minute_length = radius * 0.75
        minute_x = center_x + int(minute_length * math.cos(minute_angle))
        minute_y = center_y + int(minute_length * math.sin(minute_angle))
        draw.line([(center_x, center_y), (minute_x, minute_y)], fill=BLACK, width=4)

        # Second hand
        second = now.second
        second_angle = math.radians(second * 6 - 90)
        second_length = radius * 0.85
        second_x = center_x + int(second_length * math.cos(second_angle))
        second_y = center_y + int(second_length * math.sin(second_angle))
        draw.line(
            [(center_x, center_y), (second_x, second_y)], fill=(200, 0, 0), width=2
        )

        # Center dot
        draw.ellipse(
            [(center_x - 6, center_y - 6), (center_x + 6, center_y + 6)],
            fill=BLACK,
        )
        draw.ellipse(
            [(center_x - 3, center_y - 3), (center_x + 3, center_y + 3)],
            fill=(200, 0, 0),
        )
