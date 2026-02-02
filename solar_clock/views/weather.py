"""Weather view - current conditions and forecast."""

import datetime

from PIL import Image, ImageDraw

from .base import (
    BaseView,
    UPDATE_FREQUENT,
    YELLOW,
    ORANGE,
    BLUE,
    LIGHT_BLUE,
    FontSize,
    Layout,
)


class WeatherView(BaseView):
    """Weather view with current conditions and 3-day forecast."""

    name = "weather"
    title = "Weather"
    update_interval = UPDATE_FREQUENT

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the weather view content."""
        theme = self.get_theme()

        # Header
        self.render_header(draw, "Weather", LIGHT_BLUE)

        # Current conditions (left side)
        self._render_current_conditions(draw, Layout.CONTENT_START)

        # Forecast (right side)
        self._render_forecast(draw, Layout.CONTENT_START)

        # Location and weather description
        font_small = self.get_font(14)
        font_desc = self.get_font(16)
        location = self.config.location.name

        # Weather description below current conditions panel (truncate if needed)
        if self.providers.weather:
            weather = self.providers.weather.get_current_weather()
            if weather:
                desc = weather.description
                max_width = 200  # Limit to left panel width
                desc_bbox = draw.textbbox((0, 0), desc, font=font_desc)
                if desc_bbox[2] - desc_bbox[0] > max_width:
                    # Truncate and add ellipsis
                    while (
                        len(desc) > 3
                        and draw.textbbox((0, 0), desc + "...", font=font_desc)[2]
                        > max_width
                    ):
                        desc = desc[:-1]
                    desc = desc.rstrip() + "..."
                draw.text((20, 170), desc, fill=YELLOW, font=font_desc)

        draw.text(
            (20, self.content_height - 25),
            location,
            fill=theme.text_tertiary,
            font=font_small,
        )

    def _render_current_conditions(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render current weather conditions."""
        font_large = self.get_bold_font(48)
        font_small = self.get_font(14)
        theme = self.get_theme()

        x = 20

        if self.providers.weather is None:
            self.render_centered_message(draw, "Weather data unavailable")
            return

        weather = self.providers.weather.get_current_weather()
        if weather is None:
            self.render_centered_message(draw, "Weather data unavailable")
            return

        # Subtle background panel for current conditions
        draw.rounded_rectangle(
            ((10, y - 5), (160, y + 120)), radius=8, fill=theme.background_panel
        )

        # Temperature - larger and bolder
        temp = f"{weather.temperature:.0f}°F"
        draw.text((x, y + 5), temp, fill=theme.text_primary, font=font_large)

        # Feels like
        feels = f"Feels {weather.feels_like:.0f}°"
        draw.text((x, y + 58), feels, fill=theme.text_secondary, font=font_small)

        # Humidity with icon
        humidity = f"Humidity {weather.humidity}%"
        draw.text((x, y + 78), humidity, fill=theme.text_secondary, font=font_small)

        # Wind
        wind = f"Wind {weather.wind_speed:.0f} {weather.wind_direction}"
        draw.text((x, y + 98), wind, fill=theme.text_secondary, font=font_small)

    def _render_forecast(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render 3-day forecast."""
        font_header = self.get_font(FontSize.CAPTION)
        font_day = self.get_font(16)
        font_temp = self.get_bold_font(18)
        theme = self.get_theme()

        # Forecast panel background
        x_start = 175
        draw.rounded_rectangle(
            ((170, y - 5), (self.width - 10, y + 175)),
            radius=8,
            fill=theme.background_panel,
        )

        # Table headers
        draw.text(
            (x_start + 5, y + 2), "Day", fill=theme.text_tertiary, font=font_header
        )
        draw.text(
            (x_start + 75, y + 2), "Hi", fill=theme.text_tertiary, font=font_header
        )
        draw.text(
            (x_start + 125, y + 2), "Lo", fill=theme.text_tertiary, font=font_header
        )
        draw.text(
            (x_start + 175, y + 2), "Rain", fill=theme.text_tertiary, font=font_header
        )

        # Header divider
        draw.line(
            [(x_start, y + 20), (self.width - 15, y + 20)], fill=theme.divider, width=1
        )

        if self.providers.weather is None:
            return

        forecast = self.providers.weather.get_forecast(3)
        if not forecast:
            return

        row_y = y + 28
        row_height = 50

        day_names = ["Today", "Tmrw"]
        for i, day in enumerate(forecast[:3]):
            if i < 2:
                day_label = day_names[i]
            else:
                # Get day of week
                date = datetime.datetime.strptime(day.date, "%Y-%m-%d")
                day_label = date.strftime("%a")

            draw.text(
                (x_start + 5, row_y), day_label, fill=theme.text_primary, font=font_day
            )
            draw.text(
                (x_start + 70, row_y),
                f"{day.high_temp:.0f}°",
                fill=ORANGE,
                font=font_temp,
            )
            draw.text(
                (x_start + 120, row_y),
                f"{day.low_temp:.0f}°",
                fill=BLUE,
                font=font_temp,
            )

            # Rain chance with color coding
            rain = day.rain_chance
            rain_color = (
                theme.text_secondary
                if rain < 30
                else (LIGHT_BLUE if rain < 60 else BLUE)
            )
            draw.text(
                (x_start + 175, row_y),
                f"{rain}%",
                fill=rain_color,
                font=font_day,
            )

            # Row divider
            if i < 2:
                draw.line(
                    [(x_start, row_y + 28), (self.width - 15, row_y + 28)],
                    fill=theme.divider,
                    width=1,
                )

            row_y += row_height
