"""Touch input handling for Solar Smart Clock."""

import logging
import threading
import time
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .config import TouchConfig

logger = logging.getLogger(__name__)

# Try to import evdev (only available on Pi)
try:
    from evdev import InputDevice, ecodes

    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False
    logger.info("evdev not available - touch input disabled")


class TouchHandler:
    """
    Handles touch input for swipe and tap detection.

    Supports:
    - Swipe left/right for view navigation
    - Tap on nav buttons (< and >)
    """

    def __init__(
        self,
        config: "TouchConfig",
        on_next: Callable[[], None],
        on_prev: Callable[[], None],
        display_width: int = 480,
        display_height: int = 320,
        nav_bar_height: int = 40,
    ):
        """
        Initialize touch handler.

        Args:
            config: Touch configuration
            on_next: Callback for next view
            on_prev: Callback for previous view
            display_width: Display width in pixels
            display_height: Display height in pixels
            nav_bar_height: Height of navigation bar at bottom
        """
        self.config = config
        self.on_next = on_next
        self.on_prev = on_prev
        self.display_width = display_width
        self.display_height = display_height
        self.nav_bar_height = nav_bar_height

        # Touch state
        self.touch_start_x: Optional[int] = None
        self.touch_start_y: Optional[int] = None
        self.touch_start_time: Optional[float] = None
        self.current_x: int = 0
        self.current_y: int = 0

        # Debouncing - minimum time between gestures (seconds)
        self.last_gesture_time: float = 0.0
        self.gesture_cooldown: float = 0.15  # 150ms between gestures

        # Threading
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._device: Optional["InputDevice"] = None

        # Calibration for rotated display (90 degrees)
        self.raw_min = 0
        self.raw_max = 4095

    def start(self) -> bool:
        """
        Start the touch input thread.

        Returns:
            True if started successfully, False otherwise
        """
        if not EVDEV_AVAILABLE:
            logger.warning("Touch input not available (evdev not installed)")
            return False

        if not self.config.enabled:
            logger.info("Touch input disabled in config")
            return False

        try:
            self._device = InputDevice(self.config.device)
            logger.info(f"Touch device: {self._device.name}")
        except FileNotFoundError:
            logger.error(f"Touch device not found: {self.config.device}")
            return False
        except PermissionError:
            logger.error(
                f"Permission denied for {self.config.device}. "
                "Run as root or add user to 'input' group."
            )
            return False

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Touch handler started")
        return True

    def stop(self) -> None:
        """Stop the touch input thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._device:
            self._device.close()
            self._device = None
        logger.info("Touch handler stopped")

    def _run(self) -> None:
        """Main touch input loop (runs in thread)."""
        if self._device is None:
            return

        try:
            for event in self._device.read_loop():
                if not self._running:
                    break
                self._process_event(event)
        except OSError as e:
            if self._running:
                logger.error(f"Touch device error: {e}")

    def _process_event(self, event) -> None:
        """Process a single input event."""
        if event.type == ecodes.EV_ABS:
            # For 90-degree rotation: swap X and Y axes
            if event.code == ecodes.ABS_X:
                # Raw X becomes screen Y (inverted)
                self.current_y = self._transform_y(event.value)
            elif event.code == ecodes.ABS_Y:
                # Raw Y becomes screen X
                self.current_x = self._transform_x(event.value)

        elif event.type == ecodes.EV_KEY:
            if event.code == ecodes.BTN_TOUCH:
                if event.value == 1:  # Touch down
                    self._on_touch_down()
                elif event.value == 0:  # Touch up
                    self._on_touch_up()

    def _transform_x(self, raw_value: int) -> int:
        """Transform raw X coordinate for 90-degree rotation."""
        # For 90-degree rotation: raw Y becomes screen X
        normalized = (raw_value - self.raw_min) / (self.raw_max - self.raw_min)
        return int(normalized * self.display_width)

    def _transform_y(self, raw_value: int) -> int:
        """Transform raw Y coordinate for 90-degree rotation."""
        # For 90-degree rotation: raw X becomes screen Y (inverted)
        normalized = 1.0 - ((raw_value - self.raw_min) / (self.raw_max - self.raw_min))
        return int(normalized * self.display_height)

    def _on_touch_down(self) -> None:
        """Handle touch start event."""
        self.touch_start_x = self.current_x
        self.touch_start_y = self.current_y
        self.touch_start_time = time.time()

    def _on_touch_up(self) -> None:
        """Handle touch end event."""
        if self.touch_start_x is None or self.touch_start_time is None:
            return

        # Debouncing: ignore gestures that happen too quickly after previous one
        now = time.time()
        time_since_last_gesture = now - self.last_gesture_time
        if time_since_last_gesture < self.gesture_cooldown:
            logger.debug(
                f"Ignoring gesture (debounce: {time_since_last_gesture:.3f}s < "
                f"{self.gesture_cooldown}s)"
            )
            # Still reset touch state
            self.touch_start_x = None
            self.touch_start_y = None
            self.touch_start_time = None
            return

        dx = self.current_x - self.touch_start_x
        dy = self.current_y - self.touch_start_y if self.touch_start_y else 0
        elapsed = now - self.touch_start_time
        abs_dx = abs(dx)

        logger.debug(
            f"Touch end: dx={dx}, dy={dy}, elapsed={elapsed:.2f}s, "
            f"pos=({self.current_x}, {self.current_y})"
        )

        # Swipe: significant horizontal movement (distance-first, no dead zone)
        if abs_dx >= self.config.swipe_threshold:
            if dx > 0:
                logger.debug(f"Swipe right detected (dx={dx}) -> prev view")
                self.on_prev()
            else:
                logger.debug(f"Swipe left detected (dx={dx}) -> next view")
                self.on_next()
            self.last_gesture_time = now  # Update last gesture time

        # Tap: small movement AND quick duration (everything else that's quick)
        elif elapsed < self.config.tap_timeout:
            logger.debug(f"Tap detected (dx={abs_dx}, elapsed={elapsed:.2f}s)")
            self._check_nav_button_tap()
            self.last_gesture_time = now  # Update last gesture time

        # Else: slow drag with small movement - intentionally ignored

        # Reset state
        self.touch_start_x = None
        self.touch_start_y = None
        self.touch_start_time = None

    def _check_nav_button_tap(self) -> None:
        """Check if tap was on a navigation button."""
        nav_bar_top = self.display_height - self.nav_bar_height

        # Only check if tap is in nav bar area
        if self.current_y < nav_bar_top:
            return

        # Left button (< prev)
        if self.current_x < 60:
            logger.debug("Tap on prev button")
            self.on_prev()

        # Right button (> next)
        elif self.current_x > self.display_width - 60:
            logger.debug("Tap on next button")
            self.on_next()
