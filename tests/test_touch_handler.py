"""Tests for touch input handling."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from solar_clock.touch_handler import TouchHandler


class TestTouchHandler:
    """Tests for the TouchHandler class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock touch config."""
        config = MagicMock()
        config.enabled = True
        config.device = "/dev/input/event0"
        config.swipe_threshold = 80
        config.tap_threshold = 30
        config.tap_timeout = 0.4
        return config

    @pytest.fixture
    def touch_handler(self, mock_config):
        """Create a TouchHandler instance."""
        on_next = Mock()
        on_prev = Mock()
        return TouchHandler(
            config=mock_config,
            on_next=on_next,
            on_prev=on_prev,
            display_width=480,
            display_height=320,
            nav_bar_height=40,
        )

    def test_initialization(self, touch_handler, mock_config):
        """Test TouchHandler initialization."""
        assert touch_handler.config == mock_config
        assert touch_handler.display_width == 480
        assert touch_handler.display_height == 320
        assert touch_handler.nav_bar_height == 40
        assert touch_handler.touch_start_x is None
        assert touch_handler.touch_start_y is None
        assert touch_handler.touch_start_time is None
        assert touch_handler._running is False
        assert touch_handler._thread is None
        assert touch_handler._device is None

    def test_start_when_evdev_not_available(self, touch_handler):
        """Test start when evdev is not available."""
        with patch("solar_clock.touch_handler.EVDEV_AVAILABLE", False):
            result = touch_handler.start()

        assert result is False
        assert touch_handler._running is False

    def test_start_when_disabled_in_config(self, touch_handler, mock_config):
        """Test start when touch is disabled in config."""
        mock_config.enabled = False

        with patch("solar_clock.touch_handler.EVDEV_AVAILABLE", True):
            result = touch_handler.start()

        assert result is False
        assert touch_handler._running is False

    @pytest.mark.skip(reason="Requires evdev module mocking which is complex")
    def test_start_device_not_found(self, touch_handler):
        """Test start when touch device is not found."""
        pass

    @pytest.mark.skip(reason="Requires evdev module mocking which is complex")
    def test_start_permission_error(self, touch_handler):
        """Test start when permission denied for touch device."""
        pass

    @pytest.mark.skip(reason="Requires evdev module mocking which is complex")
    def test_start_success(self, touch_handler):
        """Test successful start of touch handler."""
        pass

    def test_stop(self, touch_handler):
        """Test stopping touch handler."""
        mock_device = MagicMock()
        mock_thread = MagicMock()

        touch_handler._device = mock_device
        touch_handler._thread = mock_thread
        touch_handler._running = True

        touch_handler.stop()

        assert touch_handler._running is False
        mock_thread.join.assert_called_once_with(timeout=1.0)
        mock_device.close.assert_called_once()
        assert touch_handler._device is None
        assert touch_handler._thread is None

    def test_stop_when_not_started(self, touch_handler):
        """Test stop when handler was never started."""
        # Should not raise exception
        touch_handler.stop()

        assert touch_handler._running is False

    def test_transform_x(self, touch_handler):
        """Test X coordinate transformation."""
        # Test raw value at 0
        x = touch_handler._transform_x(0)
        assert x == 0

        # Test raw value at max
        x = touch_handler._transform_x(4095)
        assert x == 480

        # Test raw value at midpoint
        x = touch_handler._transform_x(2048)
        assert 239 <= x <= 241  # ~240

    def test_transform_y(self, touch_handler):
        """Test Y coordinate transformation (inverted)."""
        # Test raw value at 0 (should map to max Y due to inversion)
        y = touch_handler._transform_y(0)
        assert y == 320

        # Test raw value at max (should map to 0)
        y = touch_handler._transform_y(4095)
        assert y == 0

        # Test raw value at midpoint
        y = touch_handler._transform_y(2048)
        assert 159 <= y <= 161  # ~160

    def test_on_touch_down(self, touch_handler):
        """Test touch down event."""
        touch_handler.current_x = 100
        touch_handler.current_y = 150

        touch_handler._on_touch_down()

        assert touch_handler.touch_start_x == 100
        assert touch_handler.touch_start_y == 150
        assert touch_handler.touch_start_time is not None

    def test_on_touch_up_swipe_left(self, touch_handler):
        """Test swipe left detection (next view)."""
        touch_handler.touch_start_x = 200
        touch_handler.touch_start_y = 150
        touch_handler.touch_start_time = 0.0
        touch_handler.current_x = 100  # Moved left 100 pixels

        with patch("time.time", return_value=0.2):
            touch_handler._on_touch_up()

        touch_handler.on_next.assert_called_once()
        touch_handler.on_prev.assert_not_called()

    def test_on_touch_up_swipe_right(self, touch_handler):
        """Test swipe right detection (prev view)."""
        touch_handler.touch_start_x = 100
        touch_handler.touch_start_y = 150
        touch_handler.touch_start_time = 0.0
        touch_handler.current_x = 200  # Moved right 100 pixels

        with patch("time.time", return_value=0.2):
            touch_handler._on_touch_up()

        touch_handler.on_prev.assert_called_once()
        touch_handler.on_next.assert_not_called()

    def test_on_touch_up_small_movement_no_action(self, touch_handler):
        """Test that small movements below threshold don't trigger swipe."""
        touch_handler.touch_start_x = 100
        touch_handler.touch_start_y = 150
        touch_handler.touch_start_time = 0.0
        touch_handler.current_x = 110  # Moved only 10 pixels
        touch_handler.current_y = 150

        with patch("time.time", return_value=0.2):
            touch_handler._on_touch_up()

        # No swipe should be detected (below 80 pixel threshold)
        touch_handler.on_next.assert_not_called()
        touch_handler.on_prev.assert_not_called()

    def test_on_touch_up_without_start(self, touch_handler):
        """Test touch up without corresponding touch down."""
        touch_handler.touch_start_x = None
        touch_handler.touch_start_time = None

        # Should not raise exception
        touch_handler._on_touch_up()

        touch_handler.on_next.assert_not_called()
        touch_handler.on_prev.assert_not_called()

    def test_check_nav_button_tap_prev(self, touch_handler):
        """Test tap on prev button (left side)."""
        touch_handler.current_x = 30  # Left side
        touch_handler.current_y = 300  # In nav bar (320 - 40 = 280)

        touch_handler._check_nav_button_tap()

        touch_handler.on_prev.assert_called_once()
        touch_handler.on_next.assert_not_called()

    def test_check_nav_button_tap_next(self, touch_handler):
        """Test tap on next button (right side)."""
        touch_handler.current_x = 450  # Right side (480 - 30)
        touch_handler.current_y = 300  # In nav bar

        touch_handler._check_nav_button_tap()

        touch_handler.on_next.assert_called_once()
        touch_handler.on_prev.assert_not_called()

    def test_check_nav_button_tap_outside_nav_bar(self, touch_handler):
        """Test tap outside nav bar area."""
        touch_handler.current_x = 240
        touch_handler.current_y = 100  # Above nav bar

        touch_handler._check_nav_button_tap()

        touch_handler.on_next.assert_not_called()
        touch_handler.on_prev.assert_not_called()

    def test_check_nav_button_tap_middle(self, touch_handler):
        """Test tap in middle of nav bar (not on buttons)."""
        touch_handler.current_x = 240  # Middle
        touch_handler.current_y = 300  # In nav bar

        touch_handler._check_nav_button_tap()

        touch_handler.on_next.assert_not_called()
        touch_handler.on_prev.assert_not_called()

    def test_on_touch_up_resets_state(self, touch_handler):
        """Test that touch up resets touch state."""
        touch_handler.touch_start_x = 100
        touch_handler.touch_start_y = 150
        touch_handler.touch_start_time = 0.0
        touch_handler.current_x = 200

        with patch("time.time", return_value=0.2):
            touch_handler._on_touch_up()

        assert touch_handler.touch_start_x is None
        assert touch_handler.touch_start_y is None
        assert touch_handler.touch_start_time is None

    def test_process_event_abs_x(self, touch_handler):
        """Test processing absolute X coordinate event."""
        # Directly test with mock constants (evdev values)
        event = Mock()
        event.type = 3  # EV_ABS
        event.code = 0  # ABS_X
        event.value = 2048

        with patch("solar_clock.touch_handler.EVDEV_AVAILABLE", True):
            with patch.dict(
                "sys.modules",
                {"evdev": MagicMock(ecodes=MagicMock(EV_ABS=3, ABS_X=0))},
            ):
                from importlib import reload

                import solar_clock.touch_handler as th_module

                reload(th_module)
                touch_handler._process_event(event)

                # ABS_X maps to current_y due to 90-degree rotation
                assert 159 <= touch_handler.current_y <= 161

    def test_process_event_abs_y(self, touch_handler):
        """Test processing absolute Y coordinate event."""
        event = Mock()
        event.type = 3  # EV_ABS
        event.code = 1  # ABS_Y
        event.value = 2048

        with patch("solar_clock.touch_handler.EVDEV_AVAILABLE", True):
            with patch.dict(
                "sys.modules",
                {"evdev": MagicMock(ecodes=MagicMock(EV_ABS=3, ABS_Y=1))},
            ):
                from importlib import reload

                import solar_clock.touch_handler as th_module

                reload(th_module)
                touch_handler._process_event(event)

                # ABS_Y maps to current_x due to 90-degree rotation
                assert 239 <= touch_handler.current_x <= 241

    def test_process_event_touch_down(self, touch_handler):
        """Test processing touch down event."""
        touch_handler.current_x = 100
        touch_handler.current_y = 150

        event = Mock()
        event.type = 1  # EV_KEY
        event.code = 330  # BTN_TOUCH
        event.value = 1  # Touch down

        with patch("solar_clock.touch_handler.EVDEV_AVAILABLE", True):
            with patch.dict(
                "sys.modules",
                {"evdev": MagicMock(ecodes=MagicMock(EV_KEY=1, BTN_TOUCH=330))},
            ):
                from importlib import reload

                import solar_clock.touch_handler as th_module

                reload(th_module)
                touch_handler._process_event(event)

                assert touch_handler.touch_start_x == 100
                assert touch_handler.touch_start_y == 150

    def test_process_event_touch_up(self, touch_handler):
        """Test processing touch up event."""
        touch_handler.touch_start_x = 100
        touch_handler.touch_start_time = 0.0
        touch_handler.current_x = 200  # Swipe right

        event = Mock()
        event.type = 1  # EV_KEY
        event.code = 330  # BTN_TOUCH
        event.value = 0  # Touch up

        with patch("solar_clock.touch_handler.EVDEV_AVAILABLE", True):
            with patch.dict(
                "sys.modules",
                {"evdev": MagicMock(ecodes=MagicMock(EV_KEY=1, BTN_TOUCH=330))},
            ):
                from importlib import reload

                import solar_clock.touch_handler as th_module

                reload(th_module)
                with patch("time.time", return_value=0.2):
                    touch_handler._process_event(event)

                # Should have triggered prev callback
                touch_handler.on_prev.assert_called_once()

    def test_tap_detection_with_timeout(self, touch_handler):
        """Test that tap is not detected if timeout exceeded."""
        touch_handler.touch_start_x = 240
        touch_handler.touch_start_y = 300
        touch_handler.touch_start_time = 0.0
        touch_handler.current_x = 240
        touch_handler.current_y = 300

        # Time exceeds tap_timeout (0.4 seconds)
        with patch("time.time", return_value=0.5):
            touch_handler._on_touch_up()

        # No tap should be detected
        touch_handler.on_next.assert_not_called()
        touch_handler.on_prev.assert_not_called()

    def test_swipe_threshold_exact(self, touch_handler):
        """Test swipe detection at exact threshold."""
        touch_handler.touch_start_x = 100
        touch_handler.touch_start_time = 0.0
        touch_handler.current_x = 181  # Exactly 81 pixels (threshold + 1)

        with patch("time.time", return_value=0.2):
            touch_handler._on_touch_up()

        # Should trigger prev (right swipe)
        touch_handler.on_prev.assert_called_once()
