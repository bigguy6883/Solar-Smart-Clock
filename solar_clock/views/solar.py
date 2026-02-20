"""Solar details view - comprehensive sun timing information."""

import datetime

from PIL import Image, ImageDraw

from .base import BaseView, UPDATE_FREQUENT, FontSize, Layout, Spacing
from .colors import YELLOW, ORANGE, PURPLE


class SolarView(BaseView):
    """Solar details view with comprehensive sun timing."""

    name = "solar"
    title = "Solar Details"
    update_interval = UPDATE_FREQUENT

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the solar details view content."""
        # Header
        self.render_header(draw, "Solar Details", ORANGE)

        # Sun times grid
        self._render_sun_times(draw, Layout.CONTENT_START)

        # Golden hour
        self._render_golden_hour(draw, 160)

        # Current position and day info
        self._render_current_info(draw, 210)

    def _render_sun_times(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render sun event times in a grid."""
        theme = self.get_theme()
        font = self.get_font(14)
        font_value = self.get_bold_font(18)

        if self.providers.solar is None:
            self.render_centered_message(draw, "Solar data unavailable")
            return

        sun_times = self.providers.solar.get_sun_times()
        if sun_times is None:
            self.render_centered_message(draw, "Solar data unavailable")
            return

        # Two columns
        col1_x = 20
        col2_x = self.width // 2 + 10

        events = [
            ("Dawn", sun_times.dawn, col1_x, y),
            ("Sunrise", sun_times.sunrise, col1_x, y + 35),
            ("Solar Noon", sun_times.noon, col1_x, y + 70),
            ("Sunset", sun_times.sunset, col2_x, y),
            ("Dusk", sun_times.dusk, col2_x, y + 35),
        ]

        for name, time, x, row_y in events:
            draw.text((x, row_y), name, fill=theme.text_tertiary, font=font)
            time_str = time.strftime("%-I:%M %p")
            color = (
                YELLOW
                if "Sun" in name
                else ORANGE if name == "Dusk" else theme.text_secondary
            )
            draw.text((x, row_y + 15), time_str, fill=color, font=font_value)

    def _render_golden_hour(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render golden hour information."""
        theme = self.get_theme()
        font = self.get_font(14)
        font_value = self.get_font(16)

        draw.text((20, y), "Golden Hour", fill=ORANGE, font=self.get_bold_font(16))

        if self.providers.solar is None:
            return

        morning, evening = self.providers.solar.get_golden_hour()

        if morning:
            morning_str = f"{morning.start.strftime('%-I:%M')} - {morning.end.strftime('%-I:%M %p')}"
            draw.text((20, y + 22), "Morning:", fill=theme.text_tertiary, font=font)
            draw.text((90, y + 22), morning_str, fill=YELLOW, font=font_value)

        if evening:
            evening_str = f"{evening.start.strftime('%-I:%M')} - {evening.end.strftime('%-I:%M %p')}"
            draw.text((250, y + 22), "Evening:", fill=theme.text_tertiary, font=font)
            draw.text((320, y + 22), evening_str, fill=ORANGE, font=font_value)

    def _render_current_info(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render current sun position and day length info."""
        theme = self.get_theme()
        font = self.get_font(FontSize.CAPTION)
        font_value = self.get_bold_font(18)
        font_small = self.get_font(FontSize.CAPTION)

        # Sun position - rounded box
        draw.rounded_rectangle(
            ((Spacing.MEDIUM, y), (155, y + 58)),
            radius=Layout.ROUNDED_RADIUS,
            fill=theme.background_panel,
        )
        draw.text((20, y + 5), "Sun Position", fill=theme.text_tertiary, font=font)

        if self.providers.solar:
            pos = self.providers.solar.get_solar_position()
            if pos:
                elev_str = f"El: {pos.elevation:.1f}°"
                az_str = f"Az: {pos.azimuth:.0f}°"
                draw.text((20, y + 22), elev_str, fill=YELLOW, font=font_value)
                draw.text((20, y + 40), az_str, fill=theme.text_secondary, font=font)

        # Day length - rounded box
        draw.rounded_rectangle(
            ((165, y), (310, y + 58)),
            radius=Layout.ROUNDED_RADIUS,
            fill=theme.background_panel,
        )
        draw.text((175, y + 5), "Day Length", fill=theme.text_tertiary, font=font)

        if self.providers.solar:
            length = self.providers.solar.get_day_length()
            change = self.providers.solar.get_day_length_change()
            if length:
                hours = int(length)
                minutes = int((length - hours) * 60)
                draw.text(
                    (175, y + 22),
                    f"{hours}h {minutes}m",
                    fill=theme.text_primary,
                    font=font_value,
                )
            if change:
                sign = "+" if change > 0 else ""
                color = YELLOW if change > 0 else PURPLE
                draw.text(
                    (175, y + 42),
                    f"{sign}{change:.1f}m vs yday",
                    fill=color,
                    font=font_small,
                )

        # Next event - rounded box
        draw.rounded_rectangle(
            ((320, y), (self.width - Spacing.MEDIUM, y + 58)),
            radius=Layout.ROUNDED_RADIUS,
            fill=theme.background_panel,
        )
        draw.text((330, y + 5), "Next Event", fill=theme.text_tertiary, font=font)

        if self.providers.solar:
            next_event = self.providers.solar.get_next_solar_event()
            if next_event:
                name, time = next_event
                now = datetime.datetime.now(time.tzinfo)
                delta = time - now
                if delta.total_seconds() < 0:
                    # Event just passed; data provider will update shortly
                    pass
                else:
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    draw.text((330, y + 22), name, fill=ORANGE, font=font_value)
                    draw.text(
                        (330, y + 42),
                        f"in {hours}h {minutes}m",
                        fill=theme.text_secondary,
                        font=font,
                    )
