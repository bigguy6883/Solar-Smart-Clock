"""Air Quality view - AQI and pollutant levels."""

import datetime
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from .base import (
    BaseView,
    WHITE,
    BLACK,
    GRAY,
    LIGHT_GRAY,
    GREEN,
    AQI_GOOD,
    AQI_MODERATE,
    AQI_UNHEALTHY_SENSITIVE,
    AQI_UNHEALTHY,
    AQI_VERY_UNHEALTHY,
    AQI_HAZARDOUS,
)

if TYPE_CHECKING:
    from ..config import Config
    from .base import DataProviders


class AirQualityView(BaseView):
    """Air quality view with AQI and pollutant breakdown."""

    name = "airquality"
    title = "Air Quality"
    update_interval = 300

    def _get_aqi_color(self, aqi: int) -> tuple[int, int, int]:
        """Get color for AQI value."""
        if aqi <= 50:
            return AQI_GOOD
        elif aqi <= 100:
            return AQI_MODERATE
        elif aqi <= 150:
            return AQI_UNHEALTHY_SENSITIVE
        elif aqi <= 200:
            return AQI_UNHEALTHY
        elif aqi <= 300:
            return AQI_VERY_UNHEALTHY
        else:
            return AQI_HAZARDOUS

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the air quality view content."""
        if self.providers.weather is None:
            self._render_no_data(draw)
            return

        aqi_data = self.providers.weather.get_air_quality()
        if aqi_data is None:
            self._render_no_data(draw)
            return

        aqi_color = self._get_aqi_color(aqi_data.aqi)

        # Header with AQI color
        draw.rectangle([(0, 0), (self.width, 35)], fill=aqi_color)
        font_title = self.get_bold_font(24)
        title_bbox = draw.textbbox((0, 0), "Air Quality", font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        # Use black text on light colors, white on dark
        title_color = BLACK if aqi_data.aqi <= 100 else WHITE
        draw.text(
            ((self.width - title_width) // 2, 5),
            "Air Quality",
            fill=title_color,
            font=font_title,
        )

        # AQI value and category (left side)
        self._render_aqi_value(draw, aqi_data.aqi, aqi_data.category, aqi_color, 50)

        # Pollutant breakdown (right side)
        self._render_pollutants(draw, aqi_data, 50)

        # Footer with location and update time
        font_small = self.get_font(14)
        location = self.config.location.name
        draw.text((10, self.content_height - 25), location, fill=GRAY, font=font_small)

        updated = datetime.datetime.fromtimestamp(aqi_data.updated_at)
        update_str = f"Updated {updated.strftime('%I:%M %p').lstrip('0')}"
        update_bbox = draw.textbbox((0, 0), update_str, font=font_small)
        update_width = update_bbox[2] - update_bbox[0]
        draw.text(
            (self.width - update_width - 10, self.content_height - 25),
            update_str,
            fill=GRAY,
            font=font_small,
        )

    def _render_no_data(self, draw: ImageDraw.ImageDraw) -> None:
        """Render view when no data available."""
        draw.rectangle([(0, 0), (self.width, 35)], fill=GRAY)
        font_title = self.get_bold_font(24)
        draw.text((150, 5), "Air Quality", fill=WHITE, font=font_title)

        font = self.get_font(20)
        draw.text((150, 120), "No data available", fill=GRAY, font=font)

    def _render_aqi_value(
        self,
        draw: ImageDraw.ImageDraw,
        aqi: int,
        category: str,
        color: tuple,
        y: int,
    ) -> None:
        """Render the main AQI value and category."""
        font_label = self.get_font(14)
        font_aqi = self.get_bold_font(56)
        font_category = self.get_bold_font(20)

        x = 25

        # Background panel
        draw.rounded_rectangle(
            [(10, y - 5), (140, y + 115)], radius=8, fill=(25, 30, 25)
        )

        # Label
        draw.text((x, y), "US EPA AQI", fill=GRAY, font=font_label)

        # AQI value - larger for emphasis
        draw.text((x, y + 18), str(aqi), fill=color, font=font_aqi)

        # Category with color
        draw.text((x, y + 85), category, fill=color, font=font_category)

    def _render_pollutants(self, draw: ImageDraw.ImageDraw, aqi_data, y: int) -> None:
        """Render pollutant breakdown with bars."""
        font_label = self.get_font(14)
        font_value = self.get_font(12)

        # Background panel
        draw.rounded_rectangle(
            [(150, y - 5), (self.width - 10, y + 165)], radius=8, fill=(25, 30, 25)
        )

        x = 165
        draw.text((x, y + 2), "Pollutants", fill=WHITE, font=self.get_bold_font(16))

        pollutants = [
            ("PM2.5", aqi_data.pm25, 50),
            ("PM10", aqi_data.pm10, 100),
            ("O3", aqi_data.o3, 100),
            ("NO2", aqi_data.no2, 50),
            ("CO", aqi_data.co, 5000),
        ]

        row_y = y + 28
        row_height = 26
        bar_width = 120
        bar_height = 16

        for name, value, max_val in pollutants:
            # Label - right aligned
            label_bbox = draw.textbbox((0, 0), name, font=font_label)
            label_width = label_bbox[2] - label_bbox[0]
            draw.text(
                (x + 45 - label_width, row_y + 1),
                name,
                fill=LIGHT_GRAY,
                font=font_label,
            )

            # Bar background with rounded corners
            bar_x = x + 55
            draw.rounded_rectangle(
                [(bar_x, row_y), (bar_x + bar_width, row_y + bar_height)],
                radius=3,
                fill=(50, 50, 55),
            )

            # Bar fill
            fill_pct = min(value / max_val, 1.0)
            fill_width = int(bar_width * fill_pct)
            if fill_width > 3:
                # Color based on percentage
                if fill_pct < 0.5:
                    bar_color = AQI_GOOD
                elif fill_pct < 0.75:
                    bar_color = AQI_MODERATE
                else:
                    bar_color = AQI_UNHEALTHY

                draw.rounded_rectangle(
                    [(bar_x, row_y), (bar_x + fill_width, row_y + bar_height)],
                    radius=3,
                    fill=bar_color,
                )

            # Value outside bar
            value_str = f"{value:.1f}"
            draw.text(
                (bar_x + bar_width + 8, row_y + 1),
                value_str,
                fill=WHITE,
                font=font_value,
            )

            row_y += row_height
