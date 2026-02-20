"""Theme system for day/night mode switching."""

import datetime
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Literal

if TYPE_CHECKING:
    from ..data import SolarProvider

logger = logging.getLogger(__name__)

ThemeMode = Literal["auto", "day", "night"]


@dataclass(frozen=True)
class Theme:
    """Color theme definition for the display."""

    # Background colors
    background: tuple[int, int, int]
    background_panel: tuple[int, int, int]
    background_panel_dark: tuple[int, int, int]

    # Text colors
    text_primary: tuple[int, int, int]
    text_secondary: tuple[int, int, int]
    text_tertiary: tuple[int, int, int]

    # Navigation colors
    nav_background: tuple[int, int, int]
    nav_button: tuple[int, int, int]
    nav_dot_active: tuple[int, int, int]
    nav_dot_inactive: tuple[int, int, int]

    # Clock face (for analog clock)
    clock_face: tuple[int, int, int]
    clock_hands: tuple[int, int, int]
    clock_markers: tuple[int, int, int]

    # Divider/outline colors
    divider: tuple[int, int, int]
    outline: tuple[int, int, int]

    # Name for identification
    name: str = "unnamed"


# Night theme (current dark theme)
NIGHT_THEME = Theme(
    name="night",
    # Backgrounds
    background=(0, 0, 0),
    background_panel=(35, 35, 40),
    background_panel_dark=(25, 30, 25),
    # Text
    text_primary=(255, 255, 255),
    text_secondary=(180, 180, 180),
    text_tertiary=(128, 128, 128),
    # Navigation
    nav_background=(0, 0, 0),
    nav_button=(60, 60, 60),
    nav_dot_active=(255, 255, 255),
    nav_dot_inactive=(128, 128, 128),
    # Clock
    clock_face=(240, 240, 230),
    clock_hands=(0, 0, 0),
    clock_markers=(50, 50, 50),
    # Dividers
    divider=(40, 40, 50),
    outline=(128, 128, 128),
)

# Day theme (new light theme)
DAY_THEME = Theme(
    name="day",
    # Backgrounds - warm cream tones
    background=(245, 243, 235),
    background_panel=(230, 228, 220),
    background_panel_dark=(220, 218, 210),
    # Text - dark for readability
    text_primary=(30, 30, 30),
    text_secondary=(80, 80, 80),
    text_tertiary=(120, 120, 120),
    # Navigation
    nav_background=(235, 233, 225),
    nav_button=(200, 198, 190),
    nav_dot_active=(30, 30, 30),
    nav_dot_inactive=(160, 160, 160),
    # Clock
    clock_face=(255, 255, 250),
    clock_hands=(30, 30, 30),
    clock_markers=(80, 80, 80),
    # Dividers
    divider=(200, 198, 190),
    outline=(180, 178, 170),
)


class ThemeManager:
    """
    Manages theme selection based on time of day or manual override.

    Uses sunrise/sunset from SolarProvider to determine day/night mode,
    with a 1-minute cache to avoid repeated calculations.
    """

    _instance: Optional["ThemeManager"] = None

    def __init__(self, solar_provider: Optional["SolarProvider"] = None):
        """
        Initialize theme manager.

        Args:
            solar_provider: SolarProvider instance for sunrise/sunset times
        """
        self._solar_provider = solar_provider
        self._mode: ThemeMode = "auto"
        self._cached_theme: Optional[Theme] = None
        self._cache_time: float = 0
        self._cache_duration: float = 60.0  # 1 minute cache

    @classmethod
    def get_instance(cls) -> Optional["ThemeManager"]:
        """Get the singleton instance if initialized."""
        return cls._instance

    @classmethod
    def initialize(
        cls, solar_provider: Optional["SolarProvider"] = None
    ) -> "ThemeManager":
        """Initialize and return the singleton instance."""
        cls._instance = cls(solar_provider)
        logger.info("ThemeManager initialized")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance. Used primarily for testing."""
        cls._instance = None

    @property
    def mode(self) -> ThemeMode:
        """Get current theme mode."""
        return self._mode

    def set_mode(self, mode: ThemeMode) -> None:
        """
        Set theme mode.

        Args:
            mode: "auto", "day", or "night"
        """
        if mode not in ("auto", "day", "night"):
            raise ValueError(f"Invalid theme mode: {mode}")
        self._mode = mode
        self._cached_theme = None  # Invalidate cache
        logger.info(f"Theme mode set to: {mode}")

    def _fallback_is_daytime(self) -> bool:
        """Fallback daytime check using fixed hour thresholds."""
        return 6 <= datetime.datetime.now().hour < 20

    def is_daytime(self) -> bool:
        """
        Determine if it's currently daytime based on sunrise/sunset.

        Returns:
            True if between sunrise and sunset, False otherwise
        """
        if self._solar_provider is None:
            return self._fallback_is_daytime()

        try:
            sun_times = self._solar_provider.get_sun_times()
            if sun_times is None:
                return self._fallback_is_daytime()

            # Check if sunrise has a valid tzinfo
            if sun_times.sunrise is None or sun_times.sunset is None:
                return self._fallback_is_daytime()

            # Handle timezone - may be None or a tzinfo instance
            tzinfo = getattr(sun_times.sunrise, "tzinfo", None)
            if tzinfo is not None:
                try:
                    now = datetime.datetime.now(tzinfo)
                except (TypeError, AttributeError):
                    # tzinfo is not a valid timezone object (e.g., MagicMock in tests)
                    now = datetime.datetime.now()
            else:
                now = datetime.datetime.now()

            return sun_times.sunrise <= now <= sun_times.sunset
        except (TypeError, AttributeError):
            # Fallback for any unexpected errors (e.g., mock objects in tests)
            return self._fallback_is_daytime()

    def get_current_theme(self) -> Theme:
        """
        Get the current theme based on mode and time.

        Uses caching to avoid repeated calculations.

        Returns:
            Current Theme instance
        """
        now = time.time()

        # Check cache validity
        if (
            self._cached_theme is not None
            and (now - self._cache_time) < self._cache_duration
        ):
            return self._cached_theme

        # Determine theme
        if self._mode == "day":
            theme = DAY_THEME
        elif self._mode == "night":
            theme = NIGHT_THEME
        else:  # auto
            theme = DAY_THEME if self.is_daytime() else NIGHT_THEME

        # Update cache
        self._cached_theme = theme
        self._cache_time = now

        return theme

    def get_status(self) -> dict:
        """
        Get current theme status for API response.

        Returns:
            Dictionary with mode, active_theme, and is_daytime
        """
        theme = self.get_current_theme()
        return {
            "mode": self._mode,
            "active_theme": theme.name,
            "is_daytime": self.is_daytime(),
        }


def get_theme() -> Theme:
    """
    Get the current theme from the global ThemeManager.

    Falls back to NIGHT_THEME if ThemeManager not initialized.

    Returns:
        Current Theme instance
    """
    manager = ThemeManager.get_instance()
    if manager is None:
        return NIGHT_THEME
    return manager.get_current_theme()
