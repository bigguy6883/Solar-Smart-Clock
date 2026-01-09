"""Color definitions organized semantically for consistent theming."""


class Colors:
    """Semantic color organization for the Solar Smart Clock."""

    class UI:
        """UI component colors."""

        BACKGROUND = (0, 0, 0)
        PANEL_DARK = (25, 30, 25)
        PANEL_LIGHT = (35, 35, 40)
        PANEL_MEDIUM = (30, 30, 30)

    class Text:
        """Text colors."""

        PRIMARY = (255, 255, 255)
        SECONDARY = (180, 180, 180)
        TERTIARY = (128, 128, 128)

    class Solar:
        """Solar/sun related colors."""

        SUN = (255, 220, 50)
        SUNRISE = (255, 220, 50)
        SUNSET = (255, 140, 0)
        GOLDEN_HOUR = (255, 140, 0)

    class Sky:
        """Sky and weather colors."""

        BLUE = (100, 149, 237)
        DARK_BLUE = (25, 25, 112)
        LIGHT_BLUE = (135, 206, 235)

    class Moon:
        """Moon related colors."""

        PHASE = (147, 112, 219)  # Purple
        YELLOW = (255, 248, 220)  # Moon yellow

    class AQI:
        """Air Quality Index colors."""

        GOOD = (0, 228, 0)
        MODERATE = (255, 255, 0)
        UNHEALTHY_SENSITIVE = (255, 126, 0)
        UNHEALTHY = (255, 0, 0)
        VERY_UNHEALTHY = (143, 63, 151)
        HAZARDOUS = (126, 0, 35)

    class Navigation:
        """Navigation bar colors."""

        BUTTON = (60, 60, 60)
        BUTTON_ACTIVE = (80, 80, 80)

    class Accent:
        """Accent colors for various uses."""

        RED = (255, 80, 80)
        GREEN = (0, 200, 0)
        ORANGE = (255, 140, 0)
        YELLOW = (255, 220, 50)
        PURPLE = (147, 112, 219)

    class Neutral:
        """Neutral grays."""

        GRAY = (128, 128, 128)
        LIGHT_GRAY = (180, 180, 180)
        DARK_GRAY = (50, 50, 50)


# Backward compatibility - export flat color names
# This allows existing code to continue using simple imports like:
# from .colors import BLACK, WHITE, etc.

# Basic colors
BLACK = Colors.UI.BACKGROUND
WHITE = Colors.Text.PRIMARY

# Solar colors
YELLOW = Colors.Solar.SUN
ORANGE = Colors.Solar.SUNSET

# Sky colors
BLUE = Colors.Sky.BLUE
DARK_BLUE = Colors.Sky.DARK_BLUE
LIGHT_BLUE = Colors.Sky.LIGHT_BLUE

# Text colors
GRAY = Colors.Neutral.GRAY
LIGHT_GRAY = Colors.Neutral.LIGHT_GRAY
DARK_GRAY = Colors.Neutral.DARK_GRAY

# Accent colors
RED = Colors.Accent.RED
PURPLE = Colors.Accent.PURPLE
GREEN = Colors.Accent.GREEN

# Special colors
MOON_YELLOW = Colors.Moon.YELLOW

# AQI colors
AQI_GOOD = Colors.AQI.GOOD
AQI_MODERATE = Colors.AQI.MODERATE
AQI_UNHEALTHY_SENSITIVE = Colors.AQI.UNHEALTHY_SENSITIVE
AQI_UNHEALTHY = Colors.AQI.UNHEALTHY
AQI_VERY_UNHEALTHY = Colors.AQI.VERY_UNHEALTHY
AQI_HAZARDOUS = Colors.AQI.HAZARDOUS

# Navigation colors
NAV_BUTTON_COLOR = Colors.Navigation.BUTTON
NAV_BUTTON_ACTIVE = Colors.Navigation.BUTTON_ACTIVE
