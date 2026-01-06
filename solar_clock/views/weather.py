"""Weather view - current conditions and forecast."""

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from .base import BaseView, WHITE, BLACK, YELLOW, ORANGE, GRAY, LIGHT_GRAY, BLUE, LIGHT_BLUE

if TYPE_CHECKING:
    from ..config import Config
    from .base import DataProviders


class WeatherView(BaseView):
    """Weather view with current conditions and 3-day forecast."""

    name = "weather"
    title = "Weather"
    update_interval = 60

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the weather view content."""
        header_color = LIGHT_BLUE

        # Header
        draw.rectangle([(0, 0), (self.width, 35)], fill=header_color)
        font_title = self.get_bold_font(24)
        title_bbox = draw.textbbox((0, 0), "Weather", font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(
            ((self.width - title_width) // 2, 5),
            "Weather",
            fill=WHITE,
            font=font_title,
        )

        # Current conditions (left side)
        self._render_current_conditions(draw, 45)

        # Forecast (right side)
        self._render_forecast(draw, 45)

        # Location
        font_small = self.get_font(14)
        location = self.config.location.name
        draw.text((10, self.content_height - 25), location, fill=GRAY, font=font_small)

    def _render_current_conditions(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render current weather conditions."""
        font_large = self.get_bold_font(42)
        font_med = self.get_font(16)
        font_small = self.get_font(14)

        x = 15

        if self.providers.weather is None:
            draw.text((x, y + 20), "--", fill=WHITE, font=font_large)
            return

        weather = self.providers.weather.get_current_weather()
        if weather is None:
            draw.text((x, y + 20), "--", fill=WHITE, font=font_large)
            return

        # Temperature
        temp = f"{weather.temperature:.0f}°F"
        draw.text((x, y), temp, fill=WHITE, font=font_large)

        # Feels like and humidity
        feels = f"Feels {weather.feels_like:.0f}°"
        humidity = f"{weather.humidity}%"
        draw.text((x, y + 50), feels, fill=LIGHT_GRAY, font=font_small)
        draw.text((x + 80, y + 50), humidity, fill=LIGHT_GRAY, font=font_small)

        # Description
        draw.text((x, y + 70), weather.description, fill=WHITE, font=font_med)

        # Wind
        wind = f"Wind: {weather.wind_speed:.0f} mph {weather.wind_direction}"
        draw.text((x, y + 95), wind, fill=LIGHT_GRAY, font=font_small)

    def _render_forecast(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render 3-day forecast."""
        font_header = self.get_font(14)
        font_day = self.get_font(16)
        font_temp = self.get_bold_font(18)

        # Table headers
        x_start = 175
        draw.text((x_start, y), "Day", fill=GRAY, font=font_header)
        draw.text((x_start + 70, y), "Hi", fill=GRAY, font=font_header)
        draw.text((x_start + 115, y), "Lo", fill=GRAY, font=font_header)
        draw.text((x_start + 160, y), "Rain", fill=GRAY, font=font_header)

        if self.providers.weather is None:
            return

        forecast = self.providers.weather.get_forecast(3)
        if not forecast:
            return

        row_y = y + 25
        row_height = 50

        day_names = ["Today", "Tmrw"]
        for i, day in enumerate(forecast[:3]):
            if i < 2:
                day_label = day_names[i]
            else:
                # Get day of week
                import datetime
                date = datetime.datetime.strptime(day.date, "%Y-%m-%d")
                day_label = date.strftime("%a")

            draw.text((x_start, row_y), day_label, fill=WHITE, font=font_day)
            draw.text(
                (x_start + 70, row_y),
                f"{day.high_temp:.0f}°",
                fill=ORANGE,
                font=font_temp,
            )
            draw.text(
                (x_start + 115, row_y),
                f"{day.low_temp:.0f}°",
                fill=BLUE,
                font=font_temp,
            )
            draw.text(
                (x_start + 160, row_y),
                f"{day.rain_chance}%",
                fill=LIGHT_GRAY,
                font=font_day,
            )

            row_y += row_height
