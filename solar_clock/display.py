"""Framebuffer display handling for Solar Smart Clock."""

import logging
from typing import TYPE_CHECKING, Optional, BinaryIO

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from .config import DisplayConfig

logger = logging.getLogger(__name__)


class Display:
    """Handles writing images to the framebuffer display."""

    def __init__(self, config: "DisplayConfig"):
        """
        Initialize display handler.

        Args:
            config: Display configuration
        """
        self.config = config
        self.width = config.width
        self.height = config.height
        self.framebuffer = config.framebuffer
        self._fb_handle: Optional[BinaryIO] = None

    def open(self) -> bool:
        """
        Open the framebuffer device.

        Returns:
            True if successful, False otherwise
        """
        try:
            self._fb_handle = open(self.framebuffer, "wb")
            logger.info(f"Opened framebuffer: {self.framebuffer}")
            return True
        except PermissionError:
            logger.error(
                f"Permission denied opening {self.framebuffer}. "
                "Run as root or add user to 'video' group."
            )
            return False
        except FileNotFoundError:
            logger.error(
                f"Framebuffer not found: {self.framebuffer}. "
                "Check display configuration and kernel overlays."
            )
            return False
        except OSError as e:
            logger.error(f"Failed to open framebuffer: {e}")
            return False

    def close(self) -> None:
        """Close the framebuffer device."""
        if self._fb_handle:
            try:
                self._fb_handle.close()
            except Exception as e:
                logger.warning(f"Error closing framebuffer: {e}")
            finally:
                self._fb_handle = None

    def write_frame(self, image: Image.Image) -> bool:
        """
        Write a PIL Image to the framebuffer.

        The image is converted to RGB565 format and written directly
        to the framebuffer device.

        Args:
            image: PIL Image to write (should be width x height RGB)

        Returns:
            True if successful, False otherwise
        """
        if self._fb_handle is None:
            logger.error("Framebuffer not open")
            return False

        try:
            # Ensure correct size
            if image.size != (self.width, self.height):
                image = image.resize(
                    (self.width, self.height), Image.Resampling.LANCZOS
                )

            # Ensure RGB mode
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Convert to RGB565
            rgb565_data = self._rgb_to_rgb565(image)

            # Write to framebuffer
            self._fb_handle.seek(0)
            self._fb_handle.write(rgb565_data)
            self._fb_handle.flush()

            return True

        except IOError as e:
            logger.error(f"Failed to write to framebuffer: {e}")
            return False

    def _rgb_to_rgb565(self, image: Image.Image) -> bytes:
        """
        Convert RGB image to RGB565 format using NumPy vectorization.

        RGB565 format:
        - Red: 5 bits (bits 11-15)
        - Green: 6 bits (bits 5-10)
        - Blue: 5 bits (bits 0-4)

        Args:
            image: PIL Image in RGB mode

        Returns:
            Bytes in RGB565 format (little-endian)
        """
        # Convert PIL image to numpy array (H, W, 3) with uint16 for bit ops
        arr = np.array(image, dtype=np.uint16)

        # Extract color channels
        r = arr[:, :, 0]
        g = arr[:, :, 1]
        b = arr[:, :, 2]

        # Convert to RGB565: RRRRR GGGGGG BBBBB
        rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

        # Convert to little-endian bytes
        return rgb565.astype("<u2").tobytes()

    def clear(self, color: tuple[int, int, int] = (0, 0, 0)) -> bool:
        """
        Clear the display to a solid color.

        Args:
            color: RGB tuple for the fill color

        Returns:
            True if successful, False otherwise
        """
        image = Image.new("RGB", (self.width, self.height), color)
        return self.write_frame(image)

    def __enter__(self) -> "Display":
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
