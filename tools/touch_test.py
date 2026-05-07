#!/usr/bin/env python3
"""Visible touch screen test for the Waveshare 3.5" TFT.

Renders a live overlay to /dev/fb1 showing every touch in real time:
  - Green crosshair where the finger currently is (while touching)
  - Blue circle at the touch-down point
  - Orange circle at the touch-up point, connected by a red line (swipe path)
  - Header line with raw and transformed coordinates
  - Footer with the last detected gesture (TAP / SWIPE LEFT / SWIPE RIGHT)
    using the same thresholds as the production touch handler.

USAGE (run on clock.local, NOT on homelab):
    sudo systemctl stop solar-clock
    cd ~/Solar-Smart-Clock
    ./venv/bin/python tools/touch_test.py
    # ...exit with Ctrl+C, then:
    sudo systemctl start solar-clock

If you get a permission error, run with sudo.
"""

import sys
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    from evdev import InputDevice, ecodes
except ImportError:
    sys.exit(
        "evdev not installed. Run with the project venv: ./venv/bin/python tools/touch_test.py"
    )

# Reuse production transforms so the test reflects real handler behavior.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solar_clock.touch_handler import TouchHandler  # noqa: E402

# --- Configuration (matches config.example.json defaults) ---
WIDTH = 480
HEIGHT = 320
NAV_BAR_HEIGHT = 40
SWIPE_THRESHOLD = 25
TAP_TIMEOUT = 0.4
TOUCH_DEVICE = "/dev/input/event0"
FRAMEBUFFER = "/dev/fb1"
FPS = 30

# --- Colors ---
BG = (10, 10, 20)
GRID = (35, 35, 55)
AXIS = (60, 60, 85)
TEXT = (220, 220, 220)
DIM = (130, 130, 150)
CURRENT = (0, 255, 0)
DOWN = (0, 180, 255)
UP = (255, 180, 0)
SWIPE_LINE = (255, 90, 90)
NAV_OUTLINE = (90, 50, 50)
GESTURE_TAP = (120, 255, 120)
GESTURE_SWIPE = (255, 140, 140)


# A throwaway TouchHandler just to borrow its _transform_x / _transform_y.
_xform = TouchHandler.__new__(TouchHandler)
_xform.raw_min = 0
_xform.raw_max = 4095
_xform.display_width = WIDTH
_xform.display_height = HEIGHT


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.raw_x = 0
        self.raw_y = 0
        self.cur_x = 0
        self.cur_y = 0
        self.touching = False
        self.down_x = None
        self.down_y = None
        self.down_t = None
        self.up_x = None
        self.up_y = None
        self.dx = 0
        self.dy = 0
        self.elapsed = 0.0
        self.gesture = "(touch the screen)"
        self.gesture_color = DIM
        self.gesture_time = 0.0


def reader(state: State) -> None:
    dev = InputDevice(TOUCH_DEVICE)
    print(f"Touch device: {dev.name} ({TOUCH_DEVICE})")
    for ev in dev.read_loop():
        if ev.type == ecodes.EV_ABS:
            with state.lock:
                # Same axis swap as production: raw X -> screen Y, raw Y -> screen X.
                if ev.code == ecodes.ABS_X:
                    state.raw_x = ev.value
                    state.cur_y = _xform._transform_y(ev.value)
                elif ev.code == ecodes.ABS_Y:
                    state.raw_y = ev.value
                    state.cur_x = _xform._transform_x(ev.value)
        elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
            with state.lock:
                if ev.value == 1:
                    state.touching = True
                    state.down_x = state.cur_x
                    state.down_y = state.cur_y
                    state.down_t = time.time()
                    state.up_x = None
                    state.up_y = None
                else:
                    state.touching = False
                    state.up_x = state.cur_x
                    state.up_y = state.cur_y
                    if state.down_t is not None:
                        state.elapsed = time.time() - state.down_t
                        state.dx = state.cur_x - (state.down_x or 0)
                        state.dy = state.cur_y - (state.down_y or 0)
                        abs_dx = abs(state.dx)
                        if abs_dx >= SWIPE_THRESHOLD:
                            label = (
                                "SWIPE RIGHT -> prev"
                                if state.dx > 0
                                else "SWIPE LEFT -> next"
                            )
                            state.gesture = f"{label}   dx={state.dx}"
                            state.gesture_color = GESTURE_SWIPE
                        elif state.elapsed < TAP_TIMEOUT:
                            zone = ""
                            nav_top = HEIGHT - NAV_BAR_HEIGHT
                            if state.cur_y >= nav_top:
                                if state.cur_x < 60:
                                    zone = "  -> PREV button"
                                elif state.cur_x > WIDTH - 60:
                                    zone = "  -> NEXT button"
                            state.gesture = f"TAP @ ({state.cur_x},{state.cur_y}){zone}"
                            state.gesture_color = GESTURE_TAP
                        else:
                            state.gesture = "slow drag - ignored"
                            state.gesture_color = DIM
                        state.gesture_time = time.time()


def rgb_to_rgb565(image: Image.Image) -> bytes:
    arr = np.array(image, dtype=np.uint16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    return rgb565.astype("<u2").tobytes()


def load_fonts():
    base = "/usr/share/fonts/truetype/dejavu"
    try:
        return (
            ImageFont.truetype(f"{base}/DejaVuSansMono-Bold.ttf", 16),
            ImageFont.truetype(f"{base}/DejaVuSansMono.ttf", 12),
            ImageFont.truetype(f"{base}/DejaVuSansMono.ttf", 10),
        )
    except OSError:
        d = ImageFont.load_default()
        return d, d, d


def main() -> None:
    state = State()
    threading.Thread(target=reader, args=(state,), daemon=True).start()

    font_lg, font_md, font_sm = load_fonts()

    try:
        fb = open(FRAMEBUFFER, "wb")
    except PermissionError:
        sys.exit(f"Permission denied on {FRAMEBUFFER}. Try: sudo {sys.argv[0]}")

    print("Touch test running. Ctrl+C to exit.")
    nav_top = HEIGHT - NAV_BAR_HEIGHT

    try:
        while True:
            img = Image.new("RGB", (WIDTH, HEIGHT), BG)
            d = ImageDraw.Draw(img)

            # Grid + center axes
            for x in range(0, WIDTH, 40):
                d.line([(x, 0), (x, HEIGHT)], fill=GRID)
            for y in range(0, HEIGHT, 40):
                d.line([(0, y), (WIDTH, y)], fill=GRID)
            d.line([(WIDTH // 2, 0), (WIDTH // 2, HEIGHT)], fill=AXIS)
            d.line([(0, HEIGHT // 2), (WIDTH, HEIGHT // 2)], fill=AXIS)

            # Nav-button zones (must match production: bottom 40px, 60px wide each side)
            d.line([(0, nav_top), (WIDTH, nav_top)], fill=NAV_OUTLINE)
            d.rectangle((0, nav_top, 60, HEIGHT - 1), outline=NAV_OUTLINE)
            d.rectangle(
                (WIDTH - 60, nav_top, WIDTH - 1, HEIGHT - 1), outline=NAV_OUTLINE
            )
            d.text((6, nav_top + 14), "PREV", fill=DIM, font=font_sm)
            d.text((WIDTH - 54, nav_top + 14), "NEXT", fill=DIM, font=font_sm)

            with state.lock:
                raw_x, raw_y = state.raw_x, state.raw_y
                cx, cy = state.cur_x, state.cur_y
                touching = state.touching
                dxp, dyp = state.down_x, state.down_y
                uxp, uyp = state.up_x, state.up_y
                gesture = state.gesture
                gcolor = state.gesture_color
                gage = time.time() - state.gesture_time if state.gesture_time else 999
                ldx, ldy, lt = state.dx, state.dy, state.elapsed

            # Touch-down marker
            if dxp is not None and dyp is not None:
                d.ellipse([dxp - 6, dyp - 6, dxp + 6, dyp + 6], outline=DOWN, width=2)
                d.text((dxp + 9, dyp - 6), "down", fill=DOWN, font=font_sm)

            # Touch-up marker + path
            if uxp is not None and uyp is not None:
                if dxp is not None:
                    d.line([(dxp, dyp), (uxp, uyp)], fill=SWIPE_LINE, width=1)
                d.ellipse([uxp - 6, uyp - 6, uxp + 6, uyp + 6], outline=UP, width=2)
                d.text((uxp + 9, uyp - 6), "up", fill=UP, font=font_sm)

            # Live crosshair while touching
            if touching:
                d.line([(cx - 14, cy), (cx + 14, cy)], fill=CURRENT, width=2)
                d.line([(cx, cy - 14), (cx, cy + 14)], fill=CURRENT, width=2)
                d.ellipse(
                    [cx - 20, cy - 20, cx + 20, cy + 20], outline=CURRENT, width=1
                )

            # Header
            d.text(
                (4, 2), "TOUCH TEST   (Ctrl+C on SSH to exit)", fill=TEXT, font=font_md
            )
            status = "TOUCHING" if touching else "        "
            d.text(
                (4, 18),
                f"raw=({raw_x:4d},{raw_y:4d})  screen=({cx:3d},{cy:3d})  {status}",
                fill=TEXT,
                font=font_md,
            )

            # Last gesture line (just above nav bar)
            d.text((4, nav_top - 36), f"Last: {gesture}", fill=gcolor, font=font_lg)
            if state.gesture_time:
                d.text(
                    (4, nav_top - 18),
                    f"   dx={ldx:+4d}  dy={ldy:+4d}  elapsed={lt:.2f}s   age={gage:.1f}s",
                    fill=DIM,
                    font=font_md,
                )

            fb.seek(0)
            fb.write(rgb_to_rgb565(img))
            fb.flush()
            time.sleep(1 / FPS)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            blank = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
            fb.seek(0)
            fb.write(rgb_to_rgb565(blank))
            fb.flush()
            fb.close()
        except Exception:
            pass
        print("\nExited.")


if __name__ == "__main__":
    main()
