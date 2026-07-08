"""Day Length view - yearly day length chart."""

import datetime
import math

from PIL import Image, ImageDraw

from .base import BaseView, UPDATE_HOURLY, FontSize
from .colors import ORANGE


class DayLengthView(BaseView):
    """Day length view showing yearly variation."""

    name = "daylength"
    title = "Day Length"
    update_interval = UPDATE_HOURLY

    # Chart y-axis range (hours of daylight)
    CHART_MIN_HOURS = 9
    CHART_MAX_HOURS = 15

    def render_content(self, draw: ImageDraw.ImageDraw, image: Image.Image) -> None:
        """Render the day length view content."""
        # Header
        self.render_header(draw, "Day Length", ORANGE)

        # Day length curve
        self._render_yearly_curve(draw, 45)

        # Info boxes
        self._render_info_boxes(draw, self.content_height - 65)

    def _render_yearly_curve(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render the yearly day length curve."""
        theme = self.get_theme()
        chart_x = 30
        chart_width = self.width - 40
        chart_height = 100
        chart_y = y

        font_tiny = self.get_font(FontSize.AXIS_LABEL)

        # Y-axis labels at their true positions on the chart scale
        chart_span = self.CHART_MAX_HOURS - self.CHART_MIN_HOURS
        for hours in (14, 12, 10):
            label_y = (
                chart_y
                + chart_height
                - int(((hours - self.CHART_MIN_HOURS) / chart_span) * chart_height)
            )
            draw.text(
                (5, label_y - 5),
                f"{hours}h",
                fill=theme.text_tertiary,
                font=font_tiny,
            )

        # X-axis month labels. The curve is rotated so today sits at the
        # center of the chart, so labels start ~6 months before today.
        today = datetime.date.today()
        month_abbr = ["Ja", "F", "Mr", "Ap", "My", "Jn", "Jl", "Au", "S", "O", "N", "D"]
        start_month = (today - datetime.timedelta(days=182)).month - 1
        for i in range(12):
            month = month_abbr[(start_month + i) % 12]
            x = chart_x + int((i / 12) * chart_width)
            draw.text(
                (x, chart_y + chart_height + 2),
                month,
                fill=theme.text_tertiary,
                font=font_tiny,
            )

        # Draw day length curve (simplified sinusoidal approximation)
        points = []
        year = today.year

        # Calculate for each day of year
        for day_of_year in range(0, 365, 3):
            date = datetime.date(year, 1, 1) + datetime.timedelta(days=day_of_year)

            # Get actual day length if solar provider available
            if self.providers.solar:
                length = self.providers.solar.get_day_length(date)
                if length is None:
                    continue
            else:
                # Simplified approximation
                latitude = self.config.location.latitude
                declination = 23.45 * math.sin(
                    math.radians((360 / 365) * (day_of_year - 81))
                )
                hour_angle = math.acos(
                    -math.tan(math.radians(latitude))
                    * math.tan(math.radians(declination))
                )
                length = 2 * math.degrees(hour_angle) / 15

            # Map to chart coordinates
            # Adjust day_of_year to center on current month
            today_doy = (today - datetime.date(year, 1, 1)).days
            offset = today_doy - 182  # Center on today
            adjusted_doy = (day_of_year - offset) % 365

            x = chart_x + int((adjusted_doy / 365) * chart_width)
            # Map chart hour range to chart height
            y_pos = (
                chart_y
                + chart_height
                - int(((length - self.CHART_MIN_HOURS) / chart_span) * chart_height)
            )
            y_pos = max(chart_y, min(chart_y + chart_height, y_pos))
            points.append((x, y_pos))

        # Sort points by x coordinate
        points.sort(key=lambda p: p[0])

        # Draw curve
        if len(points) > 1:
            draw.line(points, fill=ORANGE, width=2)

        # Mark today
        today_doy = (today - datetime.date(year, 1, 1)).days
        today_x = chart_x + chart_width // 2  # Centered

        if self.providers.solar:
            today_length = self.providers.solar.get_day_length()
            if today_length:
                today_y = (
                    chart_y
                    + chart_height
                    - int(
                        ((today_length - self.CHART_MIN_HOURS) / chart_span)
                        * chart_height
                    )
                )
                draw.ellipse(
                    [(today_x - 5, today_y - 5), (today_x + 5, today_y + 5)],
                    fill=theme.text_primary,
                    outline=theme.accent_sun,
                )

    def _render_info_boxes(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """Render info boxes at bottom."""
        theme = self.get_theme()
        font = self.get_font(12)
        font_value = self.get_bold_font(18)
        font_small = self.get_font(FontSize.AXIS_LABEL)

        box_width = 150
        gap = 10

        # Box 1: Today
        draw.rounded_rectangle(
            ((10, y), (10 + box_width, y + 55)), radius=6, fill=theme.background_panel
        )
        draw.text((15, y + 3), "Today", fill=theme.text_tertiary, font=font)

        if self.providers.solar:
            length = self.providers.solar.get_day_length()
            change = self.providers.solar.get_day_length_change()
            if length:
                hours = int(length)
                minutes = int((length - hours) * 60)
                draw.text(
                    (15, y + 18),
                    f"{hours}h {minutes}m",
                    fill=theme.text_primary,
                    font=font_value,
                )
            if change:
                sign = "+" if change > 0 else ""
                draw.text(
                    (15, y + 40),
                    f"{sign}{change:.1f}m/day",
                    fill=theme.accent_sun if change > 0 else theme.accent_cool,
                    font=font_small,
                )

        # Box 2: Shortest/Longest
        x2 = 10 + box_width + gap
        draw.rounded_rectangle(
            ((x2, y), (x2 + box_width, y + 55)), radius=6, fill=theme.background_panel
        )
        draw.text(
            (x2 + 5, y + 3), "Shortest", fill=theme.text_tertiary, font=font_small
        )
        draw.text(
            (x2 + 75, y + 3), "Longest", fill=theme.text_tertiary, font=font_small
        )

        if self.providers.lunar:
            dates = self.providers.lunar.get_solstice_equinox(
                datetime.date.today().year
            )

            def fmt_length(hours_float: float) -> str:
                hours = int(hours_float)
                minutes = int((hours_float - hours) * 60)
                return f"{hours}h {minutes:02d}m"

            shortest = longest = None
            if self.providers.solar:
                shortest = self.providers.solar.get_day_length(dates.winter_solstice)
                longest = self.providers.solar.get_day_length(dates.summer_solstice)

            if shortest is not None:
                draw.text(
                    (x2 + 5, y + 15),
                    fmt_length(shortest),
                    fill=theme.accent_cool,
                    font=font,
                )
            draw.text(
                (x2 + 5, y + 30),
                dates.winter_solstice.strftime("%b %d"),
                fill=theme.text_secondary,
                font=font_small,
            )
            if longest is not None:
                draw.text(
                    (x2 + 75, y + 15),
                    fmt_length(longest),
                    fill=theme.accent_warm,
                    font=font,
                )
            draw.text(
                (x2 + 75, y + 30),
                dates.summer_solstice.strftime("%b %d"),
                fill=theme.text_secondary,
                font=font_small,
            )

        # Box 3: Next event
        x3 = x2 + box_width + gap
        draw.rounded_rectangle(
            ((x3, y), (self.width - 10, y + 55)), radius=6, fill=theme.background_panel
        )
        draw.text((x3 + 5, y + 3), "Next", fill=theme.text_tertiary, font=font)

        if self.providers.lunar:
            dates = self.providers.lunar.get_solstice_equinox(
                datetime.date.today().year
            )
            today = datetime.date.today()

            # Find next event
            events = [
                ("Vernal", dates.spring_equinox),
                ("Summer", dates.summer_solstice),
                ("Autumn", dates.fall_equinox),
                ("Winter", dates.winter_solstice),
            ]

            for name, date in events:
                if date > today:
                    days = (date - today).days
                    draw.text(
                        (x3 + 5, y + 18), name, fill=theme.accent_green, font=font
                    )
                    draw.text(
                        (x3 + 5, y + 35),
                        date.strftime("%b %d"),
                        fill=theme.text_secondary,
                        font=font_small,
                    )
                    draw.text(
                        (x3 + 70, y + 18),
                        str(days),
                        fill=theme.text_primary,
                        font=font_value,
                    )
                    draw.text(
                        (x3 + 70, y + 40),
                        "days",
                        fill=theme.text_tertiary,
                        font=font_small,
                    )
                    break
