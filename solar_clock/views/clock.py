"""Clock view - main time display with weather and sun info."""

import datetime

from PIL import Image, ImageDraw

from .base import (
    BaseView,
    YELLOW,
    ORANGE,
    UPDATE_REALTIME,
    Layout,
)


class ClockView(BaseView):
    """Main clock view with time, date, weather, and sun times."""

    name = "clock"
    title = "Clock"
    update_interval = UPDATE_REALTIME

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the clock view content."""
        now = datetime.datetime.now()
        header_color = self.get_time_header_color()
        theme = self.get_theme()

        # Header bar
        draw.rectangle(((0, 0), (self.width, 45)), fill=header_color)

        # Time display
        time_str = now.strftime("%-I:%M:%S")
        am_pm = now.strftime("%p")

        font_time = self.get_bold_font(46)
        font_ampm = self.get_font(24)

        # Center the time
        time_bbox = draw.textbbox((0, 0), time_str, font=font_time)
        time_width = time_bbox[2] - time_bbox[0]
        ampm_bbox = draw.textbbox((0, 0), am_pm, font=font_ampm)
        ampm_width = ampm_bbox[2] - ampm_bbox[0]

        total_width = time_width + ampm_width + 5
        start_x = (self.width - total_width) // 2

        draw.text((start_x, -1), time_str, fill=theme.text_primary, font=font_time)
        draw.text(
            (start_x + time_width + 5, 20),
            am_pm,
            fill=theme.text_secondary,
            font=font_ampm,
        )

        # Date
        date_str = now.strftime("%A, %B %d, %Y")
        font_date = self.get_font(18)
        date_bbox = draw.textbbox((0, 0), date_str, font=font_date)
        date_width = date_bbox[2] - date_bbox[0]
        draw.text(
            ((self.width - date_width) // 2, 55),
            date_str,
            fill=theme.text_primary,
            font=font_date,
        )

        # Sun times section
        self._render_sun_info(draw, Layout.ROW_2)

        # Weather section
        self._render_weather_info(draw, Layout.ROW_3)

        # Day progress bar
        self._render_day_progress(draw, Layout.ROW_4)

    def _render_sun_info(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render sunrise/sunset times and day length."""
        font = self.get_font(16)
        font_value = self.get_bold_font(20)
        theme = self.get_theme()

        if self.providers.solar is None:
            return

        sun_times = self.providers.solar.get_sun_times()
        if sun_times is None:
            return

        # Sunrise
        sunrise_str = sun_times.sunrise.strftime("%-I:%M %p")
        draw.text((20, y), "Sunrise", fill=theme.text_tertiary, font=font)
        draw.text((20, y + 18), sunrise_str, fill=YELLOW, font=font_value)

        # Day length
        day_length = self.providers.solar.get_day_length()
        if day_length:
            hours = int(day_length)
            minutes = int((day_length - hours) * 60)
            length_str = f"{hours}h {minutes:02d}m"

            # Center
            length_bbox = draw.textbbox((0, 0), length_str, font=font_value)
            length_width = length_bbox[2] - length_bbox[0]
            center_x = (self.width - length_width) // 2

            draw.text((center_x, y), "daylight", fill=theme.text_tertiary, font=font)
            draw.text(
                (center_x, y + 18), length_str, fill=theme.text_primary, font=font_value
            )

        # Sunset
        sunset_str = sun_times.sunset.strftime("%-I:%M %p")
        sunset_bbox = draw.textbbox((0, 0), sunset_str, font=font_value)
        sunset_width = sunset_bbox[2] - sunset_bbox[0]

        draw.text(
            (self.width - sunset_width - 20, y),
            "Sunset",
            fill=theme.text_tertiary,
            font=font,
        )
        draw.text(
            (self.width - sunset_width - 20, y + 18),
            sunset_str,
            fill=ORANGE,
            font=font_value,
        )

    def _render_weather_info(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render current weather conditions."""
        font = self.get_font(16)
        font_value = self.get_bold_font(20)
        theme = self.get_theme()

        if self.providers.weather is None:
            draw.text(
                (20, y), "Weather: unavailable", fill=theme.text_secondary, font=font
            )
            return

        weather = self.providers.weather.get_current_weather()
        if weather is None:
            draw.text(
                (20, y), "Weather: unavailable", fill=theme.text_secondary, font=font
            )
            return

        # Description and temperature
        desc = weather.description
        temp = f"{weather.temperature:.0f}°F"
        humidity = f"{weather.humidity}%"

        draw.text((20, y), desc, fill=theme.text_primary, font=font_value)
        draw.text((20, y + 28), f"Temp: {temp}", fill=YELLOW, font=font)
        draw.text(
            (150, y + 28), f"Humidity: {humidity}", fill=theme.text_secondary, font=font
        )

        # Sun position
        if self.providers.solar:
            pos = self.providers.solar.get_solar_position()
            if pos:
                # Elevation with up/down indicator
                elev_abs = abs(pos.elevation)
                elev_arrow = "↑" if pos.elevation >= 0 else "↓"

                # Calculate compass direction from azimuth
                az = pos.azimuth
                if az >= 337.5 or az < 22.5:
                    compass = "N"
                elif az < 67.5:
                    compass = "NE"
                elif az < 112.5:
                    compass = "E"
                elif az < 157.5:
                    compass = "SE"
                elif az < 202.5:
                    compass = "S"
                elif az < 247.5:
                    compass = "SW"
                elif az < 292.5:
                    compass = "W"
                else:
                    compass = "NW"

                draw.text(
                    (self.width - 115, y),
                    "Sun Position",
                    fill=theme.text_tertiary,
                    font=font,
                )
                draw.text(
                    (self.width - 115, y + 18),
                    f"El: {elev_abs:.0f}° {elev_arrow}",
                    fill=YELLOW if pos.elevation > 0 else ORANGE,
                    font=font,
                )
                draw.text(
                    (self.width - 115, y + 36),
                    f"Az: {pos.azimuth:.0f}° {compass}",
                    fill=theme.text_secondary,
                    font=font,
                )

    def _render_day_progress(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render day progress bar and next event countdown."""
        font = self.get_font(14)
        theme = self.get_theme()

        # Calculate day progress
        now = datetime.datetime.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_progress = (now - day_start).total_seconds() / 86400

        # Progress bar
        bar_width = 200
        bar_height = 12
        bar_x = (self.width - bar_width) // 2
        bar_y = y

        # Background
        draw.rectangle(
            ((bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)),
            fill=theme.text_tertiary,
            outline=theme.text_secondary,
        )

        # Progress fill
        fill_width = int(bar_width * day_progress)
        if fill_width > 0:
            draw.rectangle(
                ((bar_x, bar_y), (bar_x + fill_width, bar_y + bar_height)),
                fill=YELLOW,
            )

        # Label
        progress_text = f"{day_progress * 100:.0f}% of day"
        text_bbox = draw.textbbox((0, 0), progress_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text(
            ((self.width - text_width) // 2, y + 18),
            progress_text,
            fill=theme.text_secondary,
            font=font,
        )

        # Next event countdown
        if self.providers.solar:
            next_event = self.providers.solar.get_next_solar_event()
            if next_event and len(next_event) == 2:
                event_name, event_time = next_event
                # Handle timezone-aware event_time
                if event_time.tzinfo is not None:
                    now_tz = datetime.datetime.now(event_time.tzinfo)
                else:
                    now_tz = now
                delta = event_time - now_tz
                hours = int(delta.total_seconds() // 3600)
                minutes = int((delta.total_seconds() % 3600) // 60)

                countdown = f"{event_name} in {hours}h {minutes}m"
                countdown_bbox = draw.textbbox((0, 0), countdown, font=font)
                countdown_width = countdown_bbox[2] - countdown_bbox[0]
                draw.text(
                    ((self.width - countdown_width) // 2, y + 38),
                    countdown,
                    fill=theme.text_primary,
                    font=font,
                )
