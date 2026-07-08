"""Tests for theme accent colors and contrast."""

import pytest

from solar_clock.views.theme import DAY_THEME, NIGHT_THEME


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG relative luminance."""

    def channel(c: int) -> float:
        c_srgb = c / 255
        if c_srgb <= 0.03928:
            return c_srgb / 12.92
        return ((c_srgb + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast_ratio(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """WCAG contrast ratio between two colors."""
    l1 = _relative_luminance(c1)
    l2 = _relative_luminance(c2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


ACCENT_FIELDS = [
    "accent_sun",
    "accent_warm",
    "accent_moon",
    "accent_cool",
    "accent_green",
]


class TestAqiHeaderColors:
    """AQI header background colors must support white title text."""

    @pytest.mark.parametrize("aqi", [25, 75, 125, 175, 250, 400])
    def test_header_color_readable_with_white_text(self, aqi):
        from solar_clock.views.airquality import AirQualityView

        color = AirQualityView._get_aqi_header_color(aqi)
        ratio = _contrast_ratio((255, 255, 255), color)
        assert ratio >= 3.0, (
            f"AQI {aqi} header color {color} has contrast {ratio:.2f} "
            f"with white text (needs >= 3.0)"
        )


class TestThemeAccents:
    """Accent colors must be readable on their theme's backgrounds."""

    @pytest.mark.parametrize("theme", [DAY_THEME, NIGHT_THEME], ids=["day", "night"])
    @pytest.mark.parametrize("field", ACCENT_FIELDS)
    def test_accent_exists(self, theme, field):
        """Each theme defines the accent color."""
        color = getattr(theme, field)
        assert isinstance(color, tuple) and len(color) == 3

    @pytest.mark.parametrize("theme", [DAY_THEME, NIGHT_THEME], ids=["day", "night"])
    @pytest.mark.parametrize("field", ACCENT_FIELDS)
    def test_accent_contrast_on_backgrounds(self, theme, field):
        """Accents meet WCAG large-text contrast (3:1) on background and panels."""
        color = getattr(theme, field)
        for bg_name in ("background", "background_panel"):
            bg = getattr(theme, bg_name)
            ratio = _contrast_ratio(color, bg)
            assert ratio >= 3.0, (
                f"{theme.name} theme {field} {color} has contrast {ratio:.2f} "
                f"on {bg_name} {bg} (needs >= 3.0)"
            )
