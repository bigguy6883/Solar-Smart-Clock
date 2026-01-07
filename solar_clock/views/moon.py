"""Moon phase view - lunar cycle visualization."""

import datetime
import math
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from .base import BaseView, UPDATE_HOURLY, WHITE, BLACK, YELLOW, GRAY, LIGHT_GRAY, PURPLE, MOON_YELLOW

if TYPE_CHECKING:
    from ..config import Config
    from .base import DataProviders


class MoonView(BaseView):
    """Moon phase view with illumination and upcoming dates."""

    name = "moon"
    title = "Moon Phase"
    update_interval = UPDATE_HOURLY

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the moon phase view content."""
        # Header
        draw.rectangle([(0, 0), (self.width, 35)], fill=PURPLE)
        font_title = self.get_bold_font(24)
        title_bbox = draw.textbbox((0, 0), "Moon Phase", font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(
            ((self.width - title_width) // 2, 5),
            "Moon Phase",
            fill=WHITE,
            font=font_title,
        )

        if self.providers.lunar is None or not self.providers.lunar.available:
            self.render_centered_message(draw, "Lunar data unavailable")
            return

        moon = self.providers.lunar.get_moon_phase()
        if moon is None:
            self.render_centered_message(draw, "Lunar data unavailable")
            return

        # Moon visualization (left side)
        self._render_moon_graphic(draw, image, moon.phase, 45)

        # Phase info (right side)
        self._render_phase_info(draw, moon, 180)

        # Moon times
        self._render_moon_times(draw, 170)

        # Upcoming dates
        self._render_upcoming_dates(draw, moon, 220)

    def _render_moon_graphic(
        self, draw: ImageDraw.ImageDraw, image: Image.Image, phase: float, y: int
    ) -> None:
        """Render the moon phase graphic."""
        center_x = 90
        center_y = y + 55
        radius = 50

        # Draw full moon (background)
        draw.ellipse(
            [(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)],
            fill=MOON_YELLOW,
        )

        # Draw shadow based on phase
        # phase: 0 = new, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter
        if phase < 0.5:
            # Waxing: shadow on left, shrinking
            shadow_offset = int((0.5 - phase) * 2 * radius)
            shadow_x = center_x - shadow_offset
        else:
            # Waning: shadow on right, growing
            shadow_offset = int((phase - 0.5) * 2 * radius)
            shadow_x = center_x + shadow_offset

        # Draw shadow ellipse
        if phase < 0.03 or phase > 0.97:
            # New moon - full shadow
            draw.ellipse(
                [(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)],
                fill=(30, 30, 30),
            )
        elif 0.47 <= phase <= 0.53:
            # Full moon - no shadow
            pass
        else:
            # Partial shadow using arc
            if phase < 0.5:
                # Shadow on right side
                arc_width = int((0.5 - phase) * 2 * radius * 2)
                draw.ellipse(
                    [
                        (center_x + radius - arc_width, center_y - radius),
                        (center_x + radius, center_y + radius),
                    ],
                    fill=(30, 30, 30),
                )
            else:
                # Shadow on left side
                arc_width = int((phase - 0.5) * 2 * radius * 2)
                draw.ellipse(
                    [
                        (center_x - radius, center_y - radius),
                        (center_x - radius + arc_width, center_y + radius),
                    ],
                    fill=(30, 30, 30),
                )

        # Moon outline
        draw.ellipse(
            [(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)],
            outline=GRAY,
            width=1,
        )

    def _render_phase_info(self, draw: ImageDraw.ImageDraw, moon, x: int) -> None:
        """Render phase name and illumination."""
        font = self.get_font(14)
        font_large = self.get_bold_font(36)
        font_name = self.get_font(18)

        y = 50

        # Illumination percentage
        illum_str = f"{moon.illumination:.0f}%"
        draw.text((x, y), illum_str, fill=WHITE, font=font_large)

        # Phase name
        draw.text((x, y + 45), moon.phase_name, fill=MOON_YELLOW, font=font_name)

    def _render_moon_times(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render moonrise and moonset times."""
        font = self.get_font(12)
        font_value = self.get_font(16)

        # Background boxes
        draw.rectangle([(10, y), (155, y + 40)], fill=(30, 30, 30), outline=GRAY)
        draw.rectangle([(165, y), (310, y + 40)], fill=(30, 30, 30), outline=GRAY)
        draw.rectangle([(320, y), (self.width - 10, y + 40)], fill=(30, 30, 30), outline=GRAY)

        draw.text((20, y + 5), "Moonrise", fill=GRAY, font=font)
        draw.text((175, y + 5), "Moonset", fill=GRAY, font=font)
        draw.text((330, y + 5), "Lunar Cycle", fill=GRAY, font=font)

        # Lunar cycle progress bar
        if self.providers.lunar:
            moon_data = self.providers.lunar.get_moon_phase()
            if moon_data:
                bar_x = 330
                bar_width = self.width - 10 - bar_x - 10
                bar_y = y + 22
                bar_height = 10
                # Background
                draw.rectangle([(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)], fill=(50, 50, 50))
                # Progress (phase 0-1, where 0.5 is full moon)
                fill_width = int(moon_data.phase * bar_width)
                if fill_width > 0:
                    draw.rectangle([(bar_x, bar_y), (bar_x + fill_width, bar_y + bar_height)], fill=PURPLE)
                # Full moon marker at center
                full_x = bar_x + bar_width // 2
                draw.line([(full_x, bar_y - 2), (full_x, bar_y + bar_height + 2)], fill=MOON_YELLOW, width=2)

        if self.providers.lunar:
            times = self.providers.lunar.get_moon_times()
            if times:
                if times.moonrise:
                    rise_str = times.moonrise.strftime("%-I:%M %p")
                    draw.text((20, y + 22), rise_str, fill=WHITE, font=font_value)
                if times.moonset:
                    set_str = times.moonset.strftime("%-I:%M %p")
                    draw.text((175, y + 22), set_str, fill=WHITE, font=font_value)

    def _render_upcoming_dates(self, draw: ImageDraw.ImageDraw, moon, y: int) -> None:
        """Render upcoming new and full moon dates."""
        font = self.get_font(12)
        font_value = self.get_bold_font(18)
        font_days = self.get_font(14)

        # New moon box - dark panel
        draw.rounded_rectangle([(10, y), (235, y + 48)], radius=6, fill=(35, 35, 45))
        draw.text((20, y + 5), "New Moon", fill=GRAY, font=font)
        draw.text((20, y + 24), moon.next_new.strftime("%b %d"), fill=WHITE, font=font_value)
        draw.text((120, y + 24), f"{moon.days_to_new}d", fill=LIGHT_GRAY, font=font_days)

        # Full moon box - matching dark panel with yellow accent
        draw.rounded_rectangle([(245, y), (self.width - 10, y + 48)], radius=6, fill=(35, 35, 45))
        draw.text((255, y + 5), "Full Moon", fill=GRAY, font=font)
        draw.text((255, y + 24), moon.next_full.strftime("%b %d"), fill=MOON_YELLOW, font=font_value)
        draw.text((355, y + 24), f"{moon.days_to_full}d", fill=LIGHT_GRAY, font=font_days)
