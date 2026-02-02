"""Day Length view - yearly day length chart."""

import datetime
import math

from PIL import Image, ImageDraw

from .base import (
    BaseView,
    UPDATE_HOURLY,
    WHITE,
    YELLOW,
    ORANGE,
    BLUE,
    GREEN,
    FontSize,
)


class DayLengthView(BaseView):
    """Day length view showing yearly variation."""

    name = "daylength"
    title = "Day Length"
    update_interval = UPDATE_HOURLY

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

        # Y-axis labels
        draw.text((5, chart_y), "13h", fill=theme.text_tertiary, font=font_tiny)
        draw.text(
            (5, chart_y + chart_height // 2),
            "12h",
            fill=theme.text_tertiary,
            font=font_tiny,
        )
        draw.text(
            (5, chart_y + chart_height - 10),
            "11h",
            fill=theme.text_tertiary,
            font=font_tiny,
        )

        # X-axis month labels
        months = ["Jl", "Au", "S", "O", "N", "D", "Ja", "F", "Mr", "Ap", "My", "Jn"]
        for i, month in enumerate(months):
            x = chart_x + int((i / 12) * chart_width)
            draw.text(
                (x, chart_y + chart_height + 2),
                month,
                fill=theme.text_tertiary,
                font=font_tiny,
            )

        # Draw day length curve (simplified sinusoidal approximation)
        points = []
        today = datetime.date.today()
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
            # Map 9h-15h to chart height
            y_pos = chart_y + chart_height - int(((length - 9) / 6) * chart_height)
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
                    - int(((today_length - 9) / 6) * chart_height)
                )
                draw.ellipse(
                    [(today_x - 5, today_y - 5), (today_x + 5, today_y + 5)],
                    fill=WHITE,
                    outline=YELLOW,
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
                    fill=YELLOW if change > 0 else BLUE,
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
            draw.text((x2 + 5, y + 15), "9h 49m", fill=BLUE, font=font)
            draw.text(
                (x2 + 5, y + 30),
                dates.winter_solstice.strftime("%b %d"),
                fill=theme.text_secondary,
                font=font_small,
            )
            draw.text((x2 + 75, y + 15), "14h 28m", fill=ORANGE, font=font)
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
                    draw.text((x3 + 5, y + 18), name, fill=GREEN, font=font)
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
