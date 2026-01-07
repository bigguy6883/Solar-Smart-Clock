"""Sun Path view - sun trajectory visualization."""

import datetime
import math
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from .base import BaseView, WHITE, BLACK, YELLOW, ORANGE, GRAY, LIGHT_GRAY, DARK_BLUE, LIGHT_BLUE

if TYPE_CHECKING:
    from ..config import Config
    from .base import DataProviders


class SunPathView(BaseView):
    """Sun path view showing sun trajectory across the sky."""

    name = "sunpath"
    title = "Sun Path"
    update_interval = 60

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the sun path view content."""
        # Header
        draw.rectangle([(0, 0), (self.width, 35)], fill=ORANGE)
        font_title = self.get_bold_font(24)
        title_bbox = draw.textbbox((0, 0), "Sun Path", font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(
            ((self.width - title_width) // 2, 5),
            "Sun Path",
            fill=WHITE,
            font=font_title,
        )

        # Time and date in header corners
        now = datetime.datetime.now()
        font_small = self.get_font(14)
        time_str = now.strftime("%I:%M %p").lstrip("0")
        date_str = now.strftime("%a %b %d")
        draw.text((10, 40), time_str, fill=WHITE, font=font_small)
        draw.text((self.width - 80, 40), date_str, fill=WHITE, font=font_small)

        # Sun path chart
        self._render_sun_chart(draw, image, 60)

        # Info boxes at bottom
        self._render_info_boxes(draw, self.content_height - 65)

    def _render_sun_chart(self, draw: ImageDraw.ImageDraw, image: Image.Image, y: int) -> None:
        """Render the sun elevation chart."""
        chart_height = 120
        chart_y = y + 10

        # Y-axis labels
        font_tiny = self.get_font(10)
        draw.text((5, chart_y), "40°", fill=GRAY, font=font_tiny)
        draw.text((10, chart_y + chart_height // 2), "0°", fill=GRAY, font=font_tiny)
        draw.text((5, chart_y + chart_height - 10), "-90°", fill=GRAY, font=font_tiny)

        # X-axis labels (hours)
        chart_x = 30
        chart_width = self.width - 40

        for hour in [0, 6, 12, 18, 24]:
            x = chart_x + int((hour / 24) * chart_width)
            label = f"{hour:02d}"
            draw.text((x - 8, chart_y + chart_height + 2), label, fill=GRAY, font=font_tiny)

        # Horizon line
        horizon_y = chart_y + chart_height // 2 + 20
        draw.line([(chart_x, horizon_y), (chart_x + chart_width, horizon_y)], fill=GRAY, width=1)

        # Draw sun path curve
        if self.providers.solar:
            self._draw_sun_curve(draw, chart_x, chart_y, chart_width, chart_height)

    def _draw_sun_curve(
        self, draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int
    ) -> None:
        """Draw the sun elevation curve for today."""
        if self.providers.solar is None:
            return

        points = []
        now = datetime.datetime.now()
        today = now.date()

        # Sample every 30 minutes
        for minutes in range(0, 24 * 60, 30):
            dt = datetime.datetime.combine(today, datetime.time()) + datetime.timedelta(minutes=minutes)
            dt = dt.replace(tzinfo=now.astimezone().tzinfo)

            pos = self.providers.solar.get_solar_position(dt)
            if pos:
                # Map time to x
                px = x + int((minutes / (24 * 60)) * width)
                # Map elevation to y (40 at top, -90 at bottom)
                elev_range = 40 - (-90)
                py = y + int(((40 - pos.elevation) / elev_range) * height)
                points.append((px, py))

        # Draw curve
        if len(points) > 1:
            # Draw below horizon in blue, above in yellow
            horizon_y = y + int((40 / 130) * height)

            for i in range(len(points) - 1):
                p1, p2 = points[i], points[i + 1]
                if p1[1] > horizon_y and p2[1] > horizon_y:
                    color = DARK_BLUE
                else:
                    color = YELLOW
                draw.line([p1, p2], fill=color, width=2)

        # Current sun position
        current_pos = self.providers.solar.get_solar_position()
        if current_pos:
            minutes_now = now.hour * 60 + now.minute
            cx = x + int((minutes_now / (24 * 60)) * width)
            elev_range = 40 - (-90)
            cy = y + int(((40 - current_pos.elevation) / elev_range) * height)

            # Sun marker
            draw.ellipse([(cx - 8, cy - 8), (cx + 8, cy + 8)], fill=YELLOW, outline=ORANGE)

    def _render_info_boxes(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render info boxes at bottom."""
        font = self.get_font(14)
        font_value = self.get_bold_font(20)

        # Left box: Next event countdown
        draw.rectangle([(10, y), (230, y + 55)], fill=(30, 30, 30), outline=GRAY)

        if self.providers.solar:
            next_event = self.providers.solar.get_next_solar_event()
            if next_event:
                event_name, event_time = next_event
                now = datetime.datetime.now(event_time.tzinfo)
                delta = event_time - now
                hours = int(delta.total_seconds() // 3600)
                minutes = int((delta.total_seconds() % 3600) // 60)

                draw.text((20, y + 5), event_name, fill=ORANGE, font=font)
                draw.text((115, y + 5), f"in {hours}h {minutes}m", fill=WHITE, font=font)
                draw.text((20, y + 30), f"at {event_time.strftime('%I:%M %p').lstrip('0')}", fill=LIGHT_GRAY, font=font)

        # Right box: Current elevation
        draw.rectangle([(250, y), (self.width - 10, y + 55)], fill=(30, 30, 30), outline=GRAY)

        if self.providers.solar:
            pos = self.providers.solar.get_solar_position()
            if pos:
                elev_str = f"El {pos.elevation:.0f}°"
                az_str = f"Az {pos.azimuth:.0f}°"
                draw.text((260, y + 8), elev_str, fill=YELLOW, font=font_value)
                draw.text((260, y + 32), az_str, fill=LIGHT_GRAY, font=font)
