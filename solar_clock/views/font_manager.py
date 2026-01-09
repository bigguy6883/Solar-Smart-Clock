"""Font manager singleton for centralized font caching."""

import logging
from typing import Union

from PIL import ImageFont

logger = logging.getLogger(__name__)

# Font paths (in order of preference)
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Debian/Ubuntu/Raspbian
    "/usr/share/fonts/TTF/DejaVuSans.ttf",  # Arch Linux
    "/System/Library/Fonts/Helvetica.ttc",  # macOS
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",  # Alternative Linux path
]

BOLD_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Debian/Ubuntu/Raspbian
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",  # Arch Linux
    "/System/Library/Fonts/Helvetica.ttc",  # macOS (bold variant)
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",  # Alternative Linux path
]


class FontManager:
    """
    Singleton font manager for centralized font caching.

    This eliminates per-view font cache duplication and provides
    a global font cache accessible to all views.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the font manager (only once)."""
        if not FontManager._initialized:
            self._fonts: dict[
                int, Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]
            ] = {}
            self._bold_fonts: dict[
                int, Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]
            ] = {}
            self._preload_common_sizes()
            FontManager._initialized = True
            logger.debug("FontManager singleton initialized")

    def _preload_common_sizes(self) -> None:
        """Preload commonly used font sizes for faster rendering."""
        common_sizes = [10, 12, 14, 16, 18, 20, 24, 36, 48]
        for size in common_sizes:
            # Preload both regular and bold fonts
            self.get_font(size)
            self.get_bold_font(size)
        logger.debug(f"Preloaded {len(common_sizes)} font sizes")

    def get_font(self, size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """
        Get a font at the specified size.

        Uses DejaVu Sans as the default font, with fallbacks for different
        platforms. Falls back to PIL default if no system fonts available.

        Args:
            size: Font size in points

        Returns:
            PIL ImageFont
        """
        if size not in self._fonts:
            for path in FONT_PATHS:
                try:
                    self._fonts[size] = ImageFont.truetype(path, size)
                    break
                except OSError:
                    continue
            else:
                # No fonts found, use PIL default
                self._fonts[size] = ImageFont.load_default()
                logger.warning(f"No system fonts found for size {size}, using default")
        return self._fonts[size]

    def get_bold_font(
        self, size: int
    ) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """
        Get a bold font at the specified size.

        Tries multiple font paths, falling back to regular font if bold unavailable.

        Args:
            size: Font size in points

        Returns:
            PIL ImageFont
        """
        if size not in self._bold_fonts:
            for path in BOLD_FONT_PATHS:
                try:
                    self._bold_fonts[size] = ImageFont.truetype(path, size)
                    break
                except OSError:
                    continue
            else:
                # No bold fonts found, fall back to regular font
                self._bold_fonts[size] = self.get_font(size)
                logger.debug(f"No bold font found for size {size}, using regular")
        return self._bold_fonts[size]

    def clear_cache(self) -> None:
        """Clear the font cache (useful for testing or memory management)."""
        self._fonts.clear()
        self._bold_fonts.clear()
        logger.debug("Font cache cleared")


# Global instance
_font_manager = FontManager()


def get_font_manager() -> FontManager:
    """
    Get the global FontManager instance.

    Returns:
        FontManager singleton instance
    """
    return _font_manager
