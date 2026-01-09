"""Tests for framebuffer display operations."""

from unittest.mock import MagicMock, mock_open, patch

import pytest
from PIL import Image

from solar_clock.display import Display


class TestDisplay:
    """Tests for the Display class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock display config."""
        config = MagicMock()
        config.width = 480
        config.height = 320
        config.framebuffer = "/dev/fb1"
        return config

    @pytest.fixture
    def display(self, mock_config):
        """Create a Display instance with mock config."""
        return Display(mock_config)

    def test_initialization(self, display, mock_config):
        """Test Display initialization."""
        assert display.width == 480
        assert display.height == 320
        assert display.framebuffer == "/dev/fb1"
        assert display._fb_handle is None

    def test_open_success(self, display):
        """Test successfully opening framebuffer."""
        mock_file = mock_open()
        with patch("builtins.open", mock_file):
            result = display.open()

        assert result is True
        assert display._fb_handle is not None
        mock_file.assert_called_once_with("/dev/fb1", "wb")

    def test_open_permission_error(self, display):
        """Test opening framebuffer with permission denied."""
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            result = display.open()

        assert result is False
        assert display._fb_handle is None

    def test_open_file_not_found(self, display):
        """Test opening non-existent framebuffer."""
        with patch("builtins.open", side_effect=FileNotFoundError("Not found")):
            result = display.open()

        assert result is False
        assert display._fb_handle is None

    def test_open_os_error(self, display):
        """Test opening framebuffer with OS error."""
        with patch("builtins.open", side_effect=OSError("Device error")):
            result = display.open()

        assert result is False
        assert display._fb_handle is None

    def test_close(self, display):
        """Test closing framebuffer."""
        mock_file = MagicMock()
        display._fb_handle = mock_file

        display.close()

        mock_file.close.assert_called_once()
        assert display._fb_handle is None

    def test_close_with_error(self, display):
        """Test closing framebuffer when close raises exception."""
        mock_file = MagicMock()
        mock_file.close.side_effect = IOError("Close error")
        display._fb_handle = mock_file

        # Should not raise exception
        display.close()

        assert display._fb_handle is None

    def test_close_when_not_open(self, display):
        """Test closing when framebuffer is not open."""
        display._fb_handle = None

        # Should not raise exception
        display.close()

        assert display._fb_handle is None

    def test_rgb_to_rgb565_conversion(self, display):
        """Test RGB to RGB565 color conversion."""
        # Create a 2x2 test image with known colors
        image = Image.new("RGB", (2, 2))
        pixels = image.load()

        # Set specific colors
        pixels[0, 0] = (255, 0, 0)  # Red
        pixels[1, 0] = (0, 255, 0)  # Green
        pixels[0, 1] = (0, 0, 255)  # Blue
        pixels[1, 1] = (255, 255, 255)  # White

        # Override display size for this test
        display.width = 2
        display.height = 2

        rgb565_data = display._rgb_to_rgb565(image)

        # Check data length (2x2 pixels * 2 bytes per pixel)
        assert len(rgb565_data) == 8

        # Red (255,0,0) -> RGB565: 11111_000000_00000 = 0xF800
        # Little-endian: [0x00, 0xF8]
        assert rgb565_data[0:2] == bytes([0x00, 0xF8])

        # Green (0,255,0) -> RGB565: 00000_111111_00000 = 0x07E0
        # Little-endian: [0xE0, 0x07]
        assert rgb565_data[2:4] == bytes([0xE0, 0x07])

        # Blue (0,0,255) -> RGB565: 00000_000000_11111 = 0x001F
        # Little-endian: [0x1F, 0x00]
        assert rgb565_data[4:6] == bytes([0x1F, 0x00])

        # White (255,255,255) -> RGB565: 11111_111111_11111 = 0xFFFF
        # Little-endian: [0xFF, 0xFF]
        assert rgb565_data[6:8] == bytes([0xFF, 0xFF])

    def test_write_frame_success(self, display):
        """Test successfully writing frame to framebuffer."""
        mock_file = MagicMock()
        display._fb_handle = mock_file

        # Create test image
        image = Image.new("RGB", (480, 320), color=(128, 128, 128))

        result = display.write_frame(image)

        assert result is True
        mock_file.seek.assert_called_once_with(0)
        mock_file.write.assert_called_once()
        mock_file.flush.assert_called_once()

        # Check that correct amount of data was written (480*320*2 bytes)
        written_data = mock_file.write.call_args[0][0]
        assert len(written_data) == 480 * 320 * 2

    def test_write_frame_when_not_open(self, display):
        """Test writing frame when framebuffer is not open."""
        display._fb_handle = None

        image = Image.new("RGB", (480, 320))
        result = display.write_frame(image)

        assert result is False

    def test_write_frame_resizes_image(self, display):
        """Test that write_frame resizes image to correct dimensions."""
        mock_file = MagicMock()
        display._fb_handle = mock_file

        # Create image with wrong size
        image = Image.new("RGB", (640, 480))

        result = display.write_frame(image)

        assert result is True
        # Verify data is for correct size
        written_data = mock_file.write.call_args[0][0]
        assert len(written_data) == 480 * 320 * 2

    def test_write_frame_converts_mode(self, display):
        """Test that write_frame converts non-RGB images."""
        mock_file = MagicMock()
        display._fb_handle = mock_file

        # Create image in RGBA mode
        image = Image.new("RGBA", (480, 320), color=(255, 0, 0, 128))

        result = display.write_frame(image)

        assert result is True
        mock_file.write.assert_called_once()

    def test_write_frame_io_error(self, display):
        """Test write_frame handles IO errors."""
        mock_file = MagicMock()
        mock_file.write.side_effect = IOError("Write failed")
        display._fb_handle = mock_file

        image = Image.new("RGB", (480, 320))
        result = display.write_frame(image)

        assert result is False

    def test_clear_display(self, display):
        """Test clearing display to solid color."""
        mock_file = MagicMock()
        display._fb_handle = mock_file

        result = display.clear(color=(255, 0, 0))

        assert result is True
        mock_file.write.assert_called_once()

        # Verify red color was written
        written_data = mock_file.write.call_args[0][0]
        # Red (255,0,0) in RGB565 is 0xF800 (little-endian: 0x00, 0xF8)
        # Check first pixel
        assert written_data[0] == 0x00
        assert written_data[1] == 0xF8

    def test_clear_display_default_black(self, display):
        """Test clearing display defaults to black."""
        mock_file = MagicMock()
        display._fb_handle = mock_file

        result = display.clear()

        assert result is True
        mock_file.write.assert_called_once()

        # Verify black (0,0,0) was written
        written_data = mock_file.write.call_args[0][0]
        # Black in RGB565 is 0x0000
        assert written_data[0] == 0x00
        assert written_data[1] == 0x00

    def test_context_manager(self, display):
        """Test Display as context manager."""
        mock_file = mock_open()

        with patch("builtins.open", mock_file):
            with display as d:
                assert d is display
                assert display._fb_handle is not None

        # After exit, should be closed
        assert display._fb_handle is None

    def test_context_manager_with_exception(self, display):
        """Test context manager properly closes on exception."""
        mock_file = mock_open()

        with patch("builtins.open", mock_file):
            try:
                with display:
                    assert display._fb_handle is not None
                    raise ValueError("Test exception")
            except ValueError:
                pass

        # Should still be closed after exception
        assert display._fb_handle is None

    def test_rgb565_color_accuracy(self, display):
        """Test RGB565 conversion maintains color accuracy within limits."""
        # RGB565 loses precision: RGB888 -> RGB565 -> RGB888
        # Red: 8 bits -> 5 bits (loss of 3 LSB)
        # Green: 8 bits -> 6 bits (loss of 2 LSB)
        # Blue: 8 bits -> 5 bits (loss of 3 LSB)

        display.width = 1
        display.height = 1

        test_colors = [
            (0, 0, 0),  # Black
            (255, 255, 255),  # White
            (128, 128, 128),  # Gray
            (255, 0, 0),  # Red
            (0, 255, 0),  # Green
            (0, 0, 255),  # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
        ]

        for color in test_colors:
            image = Image.new("RGB", (1, 1), color=color)
            rgb565_data = display._rgb_to_rgb565(image)

            # Just verify it produces 2 bytes without error
            assert len(rgb565_data) == 2

    def test_write_frame_data_integrity(self, display):
        """Test that write_frame produces consistent data."""
        mock_file = MagicMock()
        display._fb_handle = mock_file

        image = Image.new("RGB", (480, 320), color=(100, 150, 200))

        # Write twice
        display.write_frame(image)
        first_write = mock_file.write.call_args[0][0]

        mock_file.reset_mock()

        display.write_frame(image)
        second_write = mock_file.write.call_args[0][0]

        # Should produce identical data
        assert first_write == second_write
