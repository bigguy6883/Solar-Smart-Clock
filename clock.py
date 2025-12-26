#!/usr/bin/env python3
"""Solar Smart Clock - Multi-View with Touch Navigation"""

import os
import time
import math
import datetime
import threading
import requests
from PIL import Image, ImageDraw, ImageFont

from astral import LocationInfo
from astral.sun import sun, elevation, azimuth, golden_hour, twilight

try:
    import ephem
    EPHEM_AVAILABLE = True
except ImportError:
    EPHEM_AVAILABLE = False

try:
    import evdev
    from evdev import InputDevice, ecodes
    TOUCH_AVAILABLE = True
except ImportError:
    TOUCH_AVAILABLE = False

# Configuration
LOCATION = LocationInfo(
    name="Ellijay",
    region="GA, USA",
    timezone="America/New_York",
    latitude=34.6948,
    longitude=-84.4822
)

# Display - LANDSCAPE
WIDTH = 480
HEIGHT = 320

# Navigation bar height
NAV_BAR_HEIGHT = 40

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 220, 50)
ORANGE = (255, 140, 0)
BLUE = (100, 149, 237)
DARK_BLUE = (25, 25, 112)
LIGHT_BLUE = (135, 206, 235)
GRAY = (128, 128, 128)
DARK_GRAY = (50, 50, 50)
RED = (255, 80, 80)
PURPLE = (147, 112, 219)
MOON_YELLOW = (255, 248, 220)
NAV_BUTTON_COLOR = (60, 60, 60)
NAV_BUTTON_ACTIVE = (80, 80, 80)


class ViewManager:
    """Manages navigation between views"""
    VIEWS = ["clock", "sunpath", "weather", "moon", "solar"]

    def __init__(self):
        self.current_index = 0

    def next_view(self):
        self.current_index = (self.current_index + 1) % len(self.VIEWS)

    def prev_view(self):
        self.current_index = (self.current_index - 1) % len(self.VIEWS)

    def get_current(self):
        return self.VIEWS[self.current_index]

    def get_index(self):
        return self.current_index

    def get_count(self):
        return len(self.VIEWS)


class TouchHandler:
    """Handles touch input for swipe and tap detection with rotation support"""

    def __init__(self, view_manager, device_path="/dev/input/event0"):
        self.view_manager = view_manager
        self.device_path = device_path
        self.running = False
        self.thread = None
        self.touch_start_x = None
        self.touch_start_y = None
        self.touch_start_time = None
        
        # Touch calibration for 90-degree rotated display
        # Raw touchscreen range
        self.raw_min = 0
        self.raw_max = 4095
        
        # For 90-degree rotation: swap X/Y and invert as needed
        # These can be adjusted if touch is still misaligned
        self.swap_xy = True          # Swap X and Y axes
        self.invert_x = True        # Invert X after swap
        self.invert_y = False         # Invert Y after swap
        
        # Gesture thresholds (in screen pixels, not raw units)
        self.swipe_threshold = 60    # Minimum pixels for swipe
        self.tap_threshold = 25      # Maximum movement for tap
        self.tap_timeout = 0.5       # Maximum seconds for tap
        
        # Debug mode - set to True to see all touch coordinates
        self.debug = False
        
    def _raw_to_screen(self, raw_x, raw_y):
        """Convert raw touch coordinates to screen coordinates with rotation"""
        # Normalize to 0-1 range
        norm_x = (raw_x - self.raw_min) / (self.raw_max - self.raw_min)
        norm_y = (raw_y - self.raw_min) / (self.raw_max - self.raw_min)
        
        # Apply axis swap for rotation
        if self.swap_xy:
            norm_x, norm_y = norm_y, norm_x
        
        # Apply inversions
        if self.invert_x:
            norm_x = 1.0 - norm_x
        if self.invert_y:
            norm_y = 1.0 - norm_y
        
        # Scale to screen dimensions
        screen_x = int(norm_x * WIDTH)
        screen_y = int(norm_y * HEIGHT)
        
        # Clamp to screen bounds
        screen_x = max(0, min(WIDTH - 1, screen_x))
        screen_y = max(0, min(HEIGHT - 1, screen_y))
        
        return screen_x, screen_y

    def start(self):
        if not TOUCH_AVAILABLE:
            print("Touch not available (evdev not installed)", flush=True)
            return
        try:
            self.device = InputDevice(self.device_path)
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            print(f"Touch handler started on {self.device_path}", flush=True)
            print(f"  swap_xy={self.swap_xy}, invert_x={self.invert_x}, invert_y={self.invert_y}", flush=True)
        except Exception as e:
            print(f"Could not start touch handler: {e}", flush=True)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)

    def _run(self):
        current_x = None
        current_y = None
        touching = False
        need_start_coords = False  # Flag to capture first coords after touch down

        try:
            for event in self.device.read_loop():
                if not self.running:
                    break

                if event.type == ecodes.EV_ABS:
                    if event.code == ecodes.ABS_X:
                        current_x = event.value
                    elif event.code == ecodes.ABS_Y:
                        current_y = event.value
                    
                    # Capture start coordinates from first ABS events after touch down
                    if need_start_coords and current_x is not None and current_y is not None:
                        self.touch_start_x = current_x
                        self.touch_start_y = current_y
                        self.touch_start_time = time.time()
                        need_start_coords = False
                        if self.debug:
                            sx, sy = self._raw_to_screen(current_x, current_y)
                            print(f"Touch START: raw=({current_x}, {current_y}) -> screen=({sx}, {sy})", flush=True)

                elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
                    if event.value == 1:  # Touch down
                        touching = True
                        need_start_coords = True  # Wait for actual coordinates
                        # Reset stale values
                        current_x = None
                        current_y = None
                        if self.debug:
                            print("Touch DOWN (waiting for coords...)", flush=True)
                            
                    elif event.value == 0 and touching:  # Touch up
                        touching = False
                        need_start_coords = False
                        if self.touch_start_x is not None and current_x is not None:
                            if self.debug:
                                sx, sy = self._raw_to_screen(current_x, current_y)
                                print(f"Touch END: raw=({current_x}, {current_y}) -> screen=({sx}, {sy})", flush=True)
                            self._handle_touch(self.touch_start_x, self.touch_start_y,
                                             current_x, current_y)
                        else:
                            if self.debug:
                                print("Touch UP ignored (missing coordinates)", flush=True)
                        self.touch_start_x = None
                        self.touch_start_y = None
                        self.touch_start_time = None
                        
        except Exception as e:
            print(f"Touch handler error: {e}", flush=True)


    def _handle_touch(self, start_raw_x, start_raw_y, end_raw_x, end_raw_y):
        """Handle a complete touch gesture (touch down to touch up)"""
        # Convert to screen coordinates
        start_x, start_y = self._raw_to_screen(start_raw_x, start_raw_y)
        end_x, end_y = self._raw_to_screen(end_raw_x, end_raw_y)
        
        # Calculate deltas in screen space
        delta_x = end_x - start_x
        delta_y = end_y - start_y
        
        # Check touch duration
        duration = time.time() - self.touch_start_time if self.touch_start_time else 0
        
        if self.debug:
            print(f"Touch UP: screen=({end_x}, {end_y}) delta=({delta_x}, {delta_y}) dur={duration:.2f}s", flush=True)

        # Check for horizontal swipe first (larger horizontal movement)
        if abs(delta_x) > self.swipe_threshold and abs(delta_x) > abs(delta_y):
            if delta_x > 0:
                self.view_manager.next_view()  # Swipe right = next
                if self.debug: print(f"SWIPE RIGHT -> {self.view_manager.get_current()}", flush=True)
            else:
                self.view_manager.prev_view()  # Swipe left = prev
                if self.debug: print(f"SWIPE LEFT -> {self.view_manager.get_current()}", flush=True)
            return

        # Check for tap (small movement, quick touch)
        if abs(delta_x) < self.tap_threshold and abs(delta_y) < self.tap_threshold:
            if duration < self.tap_timeout:
                self._handle_tap(end_x, end_y)
            else:
                if self.debug:
                    print(f"Tap too slow ({duration:.2f}s > {self.tap_timeout}s)", flush=True)
        else:
            if self.debug:
                print(f"Movement too large for tap: ({abs(delta_x)}, {abs(delta_y)})", flush=True)

    def _handle_tap(self, screen_x, screen_y):
        """Handle a tap at the given screen coordinates"""
        # Check if tap is in the nav bar area (bottom NAV_BAR_HEIGHT pixels)
        if screen_y >= HEIGHT - NAV_BAR_HEIGHT - 10:  # 10px tolerance for edge
            if screen_x < 80:  # Left button area (slightly larger hit area)
                self.view_manager.prev_view()
                if self.debug: print(f"TAP left button -> {self.view_manager.get_current()}", flush=True)
                return
            elif screen_x > WIDTH - 80:  # Right button area
                self.view_manager.next_view()
                if self.debug: print(f"TAP right button -> {self.view_manager.get_current()}", flush=True)
                return
            else:
                if self.debug:
                    print(f"Tap in nav bar but not on button: x={screen_x}", flush=True)
        else:
            if self.debug:
                print(f"Tap outside nav bar: y={screen_y} (nav starts at {HEIGHT - NAV_BAR_HEIGHT})", flush=True)
class SolarClock:
    def __init__(self):
        self.fb_device = "/dev/fb1"
        self.weather_data = None
        self.weather_json = None
        self.weather_last_update = 0
        self.fonts = self._load_fonts()
        self.view_manager = ViewManager()
        self.touch_handler = TouchHandler(self.view_manager)

    def _load_fonts(self):
        fonts = {}
        font_path = None
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]:
            if os.path.exists(p):
                font_path = p
                break

        if font_path:
            fonts["huge"] = ImageFont.truetype(font_path, 54)
            fonts["large"] = ImageFont.truetype(font_path, 32)
            fonts["med"] = ImageFont.truetype(font_path, 24)
            fonts["small"] = ImageFont.truetype(font_path, 18)
            fonts["tiny"] = ImageFont.truetype(font_path, 14)
            fonts["micro"] = ImageFont.truetype(font_path, 11)
            fonts["nav"] = ImageFont.truetype(font_path, 28)
        else:
            d = ImageFont.load_default()
            fonts = {k: d for k in ["huge", "large", "med", "small", "tiny", "micro", "nav"]}
        return fonts

    def get_sun_times(self):
        try:
            return sun(LOCATION.observer, date=datetime.date.today(), tzinfo=LOCATION.timezone)
        except:
            return None

    def get_solar_position(self):
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            return elevation(LOCATION.observer, now), azimuth(LOCATION.observer, now)
        except:
            return None, None

    def get_twilight_times(self):
        """Get civil, nautical, and astronomical twilight times"""
        try:
            today = datetime.date.today()
            result = {}
            civil_dawn, civil_dusk = twilight(LOCATION.observer, today, tzinfo=LOCATION.timezone)
            result['civil'] = (civil_dawn, civil_dusk)
            return result
        except Exception as e:
            return None

    def get_golden_hour(self):
        """Get golden hour times"""
        try:
            today = datetime.date.today()
            try:
                morning = golden_hour(LOCATION.observer, today, direction=1, tzinfo=LOCATION.timezone)
            except:
                morning = None
            try:
                evening = golden_hour(LOCATION.observer, today, direction=-1, tzinfo=LOCATION.timezone)
            except:
                evening = None
            return morning, evening
        except:
            return None, None

    def get_weather(self):
        now = time.time()
        if self.weather_data and (now - self.weather_last_update) < 900:
            return self.weather_data
        try:
            r = requests.get("https://wttr.in/Ellijay,GA?format=%c+%t+%h",
                           timeout=10, headers={"User-Agent": "curl/7.0"})
            if r.status_code == 200:
                self.weather_data = r.text.strip()
                self.weather_last_update = now
        except:
            if not self.weather_data:
                self.weather_data = "--"
        return self.weather_data

    def get_weather_forecast(self):
        """Get JSON weather data for forecast view"""
        now = time.time()
        if self.weather_json and (now - self.weather_last_update) < 900:
            return self.weather_json
        try:
            r = requests.get("https://wttr.in/Ellijay,GA?format=j1",
                           timeout=10, headers={"User-Agent": "curl/7.0"})
            if r.status_code == 200:
                self.weather_json = r.json()
                self.weather_last_update = now
        except:
            pass
        return self.weather_json

    def get_moon_phase(self):
        """Calculate moon phase using ephem library"""
        if not EPHEM_AVAILABLE:
            return None

        try:
            now = datetime.datetime.now()
            moon = ephem.Moon()
            moon.compute(now)

            phase = moon.phase / 100.0
            illumination = moon.phase

            next_new = ephem.next_new_moon(now)
            next_full = ephem.next_full_moon(now)

            if phase < 0.03:
                phase_name = "New Moon"
            elif phase < 0.22:
                phase_name = "Waxing Crescent"
            elif phase < 0.28:
                phase_name = "First Quarter"
            elif phase < 0.47:
                phase_name = "Waxing Gibbous"
            elif phase < 0.53:
                phase_name = "Full Moon"
            elif phase < 0.72:
                phase_name = "Waning Gibbous"
            elif phase < 0.78:
                phase_name = "Last Quarter"
            elif phase < 0.97:
                phase_name = "Waning Crescent"
            else:
                phase_name = "New Moon"

            return {
                'phase': phase,
                'illumination': illumination,
                'phase_name': phase_name,
                'next_new': ephem.Date(next_new).datetime(),
                'next_full': ephem.Date(next_full).datetime()
            }
        except Exception as e:
            print(f"Moon phase error: {e}")
            return None

    def draw_nav_bar(self, draw):
        """Draw navigation bar with buttons and page indicators at bottom"""
        nav_y = HEIGHT - NAV_BAR_HEIGHT

        # Nav bar background
        draw.rectangle([(0, nav_y), (WIDTH, HEIGHT)], fill=BLACK)

        # Left button "<"
        btn_width = 60
        btn_height = 32
        btn_y = nav_y + (NAV_BAR_HEIGHT - btn_height) // 2

        # Left button
        draw.rounded_rectangle([(8, btn_y), (8 + btn_width, btn_y + btn_height)],
                               radius=6, fill=NAV_BUTTON_COLOR)
        draw.text((28, btn_y + 2), "<", fill=WHITE, font=self.fonts["nav"])

        # Right button
        draw.rounded_rectangle([(WIDTH - 8 - btn_width, btn_y), (WIDTH - 8, btn_y + btn_height)],
                               radius=6, fill=NAV_BUTTON_COLOR)
        draw.text((WIDTH - 8 - btn_width + 20, btn_y + 2), ">", fill=WHITE, font=self.fonts["nav"])

        # Page indicator dots in center
        count = self.view_manager.get_count()
        current = self.view_manager.get_index()

        dot_radius = 5
        dot_spacing = 20
        total_width = (count - 1) * dot_spacing
        start_x = WIDTH // 2 - total_width // 2
        dot_y = nav_y + NAV_BAR_HEIGHT // 2

        for i in range(count):
            x = start_x + i * dot_spacing
            if i == current:
                draw.ellipse([(x - dot_radius, dot_y - dot_radius),
                             (x + dot_radius, dot_y + dot_radius)], fill=WHITE)
            else:
                draw.ellipse([(x - dot_radius, dot_y - dot_radius),
                             (x + dot_radius, dot_y + dot_radius)], fill=GRAY, outline=GRAY)

    def draw_sun_arc(self, draw, elev, cx, cy, radius):
        # Horizon
        draw.line([(cx - radius, cy), (cx + radius, cy)], fill=GRAY, width=2)

        # Arc
        for i in range(0, 180, 15):
            a1, a2 = math.radians(i), math.radians(i + 15)
            x1 = cx - int(radius * math.cos(a1))
            y1 = cy - int(radius * math.sin(a1))
            x2 = cx - int(radius * math.cos(a2))
            y2 = cy - int(radius * math.sin(a2))
            draw.line([(x1, y1), (x2, y2)], fill=DARK_GRAY, width=2)

        # Sun
        if elev is not None and elev >= 0:
            angle = math.radians(180 - elev * 2)
            sx = cx - int(radius * 0.8 * math.cos(angle))
            sy = cy - int(radius * 0.8 * math.sin(angle))
            draw.ellipse([(sx-10, sy-10), (sx+10, sy+10)], fill=YELLOW, outline=WHITE)

    def draw_moon(self, draw, cx, cy, radius, phase):
        """Draw moon with phase visualization"""
        draw.ellipse([(cx - radius, cy - radius),
                     (cx + radius, cy + radius)], fill=DARK_GRAY, outline=GRAY)

        if phase is not None:
            illum = phase * 2 if phase <= 0.5 else (1 - phase) * 2

            if phase <= 0.5:
                for y_off in range(-radius, radius + 1):
                    x_edge = int(math.sqrt(max(0, radius * radius - y_off * y_off)))
                    x_inner = int(x_edge * (1 - illum * 2))
                    if x_inner < x_edge:
                        draw.line([(cx + x_inner, cy + y_off), (cx + x_edge, cy + y_off)],
                                 fill=MOON_YELLOW)
            else:
                for y_off in range(-radius, radius + 1):
                    x_edge = int(math.sqrt(max(0, radius * radius - y_off * y_off)))
                    x_inner = int(x_edge * (1 - illum * 2))
                    if x_inner < x_edge:
                        draw.line([(cx - x_edge, cy + y_off), (cx - x_inner, cy + y_off)],
                                 fill=MOON_YELLOW)

    def create_clock_frame(self):
        """Main clock view"""
        now = datetime.datetime.now()
        hour = now.hour

        if 6 <= hour < 12:
            hdr = LIGHT_BLUE
        elif 12 <= hour < 18:
            hdr = BLUE
        elif 18 <= hour < 21:
            hdr = ORANGE
        else:
            hdr = DARK_BLUE

        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header bar
        draw.rectangle([(0, 0), (WIDTH, 80)], fill=hdr)

        # Time (centered)
        time_str = now.strftime("%I:%M:%S %p")
        bbox = draw.textbbox((0, 0), time_str, font=self.fonts["huge"])
        tw = bbox[2] - bbox[0]
        draw.text((WIDTH//2 - tw//2, 5), time_str, fill=WHITE, font=self.fonts["huge"])

        # Date (centered)
        date_str = now.strftime("%A, %B %d, %Y")
        bbox = draw.textbbox((0, 0), date_str, font=self.fonts["small"])
        tw = bbox[2] - bbox[0]
        draw.text((WIDTH//2 - tw//2, 58), date_str, fill=WHITE, font=self.fonts["small"])

        # Content area: y=85 to y=HEIGHT-NAV_BAR_HEIGHT (280)
        content_bottom = HEIGHT - NAV_BAR_HEIGHT - 5

        # === LEFT SIDE: Sun times + Weather ===
        sun_times = self.get_sun_times()
        if sun_times:
            sunrise = sun_times["sunrise"].strftime("%I:%M %p")
            sunset = sun_times["sunset"].strftime("%I:%M %p")
            draw.text((15, 88), f"Rise: {sunrise}", fill=YELLOW, font=self.fonts["med"])
            draw.text((15, 114), f"Set:  {sunset}", fill=ORANGE, font=self.fonts["med"])

        # Weather box
        weather = self.get_weather()
        if weather:
            draw.rounded_rectangle([(10, 145), (220, 182)], radius=6, fill=DARK_GRAY)
            w_clean = weather.encode('ascii', 'ignore').decode()[:20]
            draw.text((18, 152), w_clean, fill=WHITE, font=self.fonts["med"])

        # Day progress
        draw.rounded_rectangle([(10, 195), (220, 215)], radius=5, fill=DARK_GRAY)
        mins = now.hour * 60 + now.minute
        prog = mins / 1440
        bw = int(206 * prog)
        if bw > 2:
            draw.rounded_rectangle([(12, 197), (12 + bw, 213)], radius=4, fill=BLUE)
        draw.text((75, 220), f"{prog*100:.0f}% of day", fill=GRAY, font=self.fonts["tiny"])

        # === RIGHT SIDE: Solar position + Arc ===
        elev, azim = self.get_solar_position()

        draw.text((245, 88), "Solar Position", fill=WHITE, font=self.fonts["med"])
        if elev is not None:
            draw.text((245, 116), f"Elev: {elev:.1f}", fill=WHITE, font=self.fonts["small"])
            draw.text((245, 138), f"Azim: {azim:.1f}", fill=WHITE, font=self.fonts["small"])

        # Sun arc
        self.draw_sun_arc(draw, elev, 360, 220, 45)

        # Navigation bar
        self.draw_nav_bar(draw)

        return img

    def get_next_solar_event(self):
        """Get the next solar event and time remaining"""
        from zoneinfo import ZoneInfo
        try:
            tz = ZoneInfo(LOCATION.timezone)
            now = datetime.datetime.now(tz)
            sun_times = self.get_sun_times()
            if not sun_times:
                return None, None, None

            # Build list of events for today
            events = []
            event_names = [
                ("dawn", "Dawn", LIGHT_BLUE),
                ("sunrise", "Sunrise", YELLOW),
                ("noon", "Solar Noon", WHITE),
                ("sunset", "Sunset", ORANGE),
                ("dusk", "Dusk", PURPLE),
            ]

            for key, name, color in event_names:
                event_time = sun_times.get(key)
                if event_time:
                    events.append((event_time, name, color, key))

            # Sort by time
            events.sort(key=lambda x: x[0])

            # Find next event
            for event_time, name, color, key in events:
                if event_time > now:
                    delta = event_time - now
                    return name, delta, color

            # All events passed - next is tomorrow's dawn
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            try:
                tomorrow_sun = sun(LOCATION.observer, date=tomorrow, tzinfo=LOCATION.timezone)
                dawn = tomorrow_sun.get("dawn")
                if dawn:
                    delta = dawn - now
                    return "Dawn (tomorrow)", delta, LIGHT_BLUE
            except:
                pass

            return None, None, None
        except Exception as e:
            print(f"Next event error: {e}")
            return None, None, None

    def create_sunpath_frame(self):
        """Sun path chart with time to next event"""
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(LOCATION.timezone)
        now = datetime.datetime.now(tz)

        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=YELLOW)
        draw.text((WIDTH//2 - 55, 6), "Sun Path", fill=BLACK, font=self.fonts["large"])

        sun_times = self.get_sun_times()
        elev, azim = self.get_solar_position()

        # Sun path chart area
        chart_cx = 160
        chart_cy = 145
        chart_radius = 85

        # Draw horizon line
        draw.line([(chart_cx - chart_radius - 10, chart_cy),
                   (chart_cx + chart_radius + 10, chart_cy)], fill=GRAY, width=2)

        # Draw compass labels
        draw.text((chart_cx - chart_radius - 25, chart_cy - 8), "E", fill=GRAY, font=self.fonts["tiny"])
        draw.text((chart_cx + chart_radius + 12, chart_cy - 8), "W", fill=GRAY, font=self.fonts["tiny"])
        draw.text((chart_cx - 5, chart_cy - chart_radius - 18), "N", fill=GRAY, font=self.fonts["tiny"])

        # Draw elevation arcs (30, 60, 90 degrees)
        for elev_line in [30, 60]:
            r = int(chart_radius * (90 - elev_line) / 90)
            draw.arc([(chart_cx - r, chart_cy - r), (chart_cx + r, chart_cy + r)],
                    180, 0, fill=DARK_GRAY)

        # Draw sun path arc for today
        if sun_times:
            sunrise = sun_times.get("sunrise")
            sunset = sun_times.get("sunset")
            noon = sun_times.get("noon")

            if sunrise and sunset and noon:
                # Draw path as series of points
                path_points = []
                for hour_offset in range(-6, 7):
                    check_time = noon + datetime.timedelta(hours=hour_offset)
                    if sunrise <= check_time <= sunset:
                        try:
                            check_utc = check_time.astimezone(datetime.timezone.utc)
                            e = elevation(LOCATION.observer, check_utc)
                            a = azimuth(LOCATION.observer, check_utc)
                            if e > 0:
                                # Map azimuth to x (E=left, W=right)
                                # Azimuth: 90=E, 180=S, 270=W
                                norm_az = (a - 90) / 180  # 0 at E, 1 at W
                                x = chart_cx - chart_radius + int(norm_az * 2 * chart_radius)
                                # Map elevation to y (higher = further from horizon)
                                y = chart_cy - int((e / 90) * chart_radius)
                                path_points.append((x, y))
                        except:
                            pass

                # Draw path
                if len(path_points) > 1:
                    for i in range(len(path_points) - 1):
                        draw.line([path_points[i], path_points[i+1]], fill=ORANGE, width=3)

                # Draw sun markers at key times
                for event_time, marker_color, label in [
                    (sunrise, YELLOW, "rise"),
                    (noon, WHITE, "noon"),
                    (sunset, ORANGE, "set")
                ]:
                    try:
                        evt_utc = event_time.astimezone(datetime.timezone.utc)
                        e = elevation(LOCATION.observer, evt_utc)
                        a = azimuth(LOCATION.observer, evt_utc)
                        norm_az = (a - 90) / 180
                        x = chart_cx - chart_radius + int(norm_az * 2 * chart_radius)
                        y = chart_cy - int((max(0, e) / 90) * chart_radius)
                        draw.ellipse([(x-4, y-4), (x+4, y+4)], fill=marker_color)
                    except:
                        pass

        # Draw current sun position
        if elev is not None and elev > 0:
            norm_az = (azim - 90) / 180
            x = chart_cx - chart_radius + int(norm_az * 2 * chart_radius)
            y = chart_cy - int((elev / 90) * chart_radius)
            # Sun glow
            draw.ellipse([(x-12, y-12), (x+12, y+12)], fill=ORANGE)
            draw.ellipse([(x-8, y-8), (x+8, y+8)], fill=YELLOW)

        # Right side: Next event countdown
        draw.text((310, 50), "Next Event", fill=WHITE, font=self.fonts["med"])

        next_event, time_delta, event_color = self.get_next_solar_event()

        if next_event and time_delta:
            # Event name
            draw.text((310, 78), next_event, fill=event_color or WHITE, font=self.fonts["large"])

            # Time remaining
            total_secs = int(time_delta.total_seconds())
            hours = total_secs // 3600
            mins = (total_secs % 3600) // 60
            secs = total_secs % 60

            if hours > 0:
                countdown = f"{hours}h {mins}m"
            else:
                countdown = f"{mins}m {secs}s"

            draw.text((310, 115), countdown, fill=WHITE, font=self.fonts["large"])

            # Progress indicator
            draw.text((310, 152), "until", fill=GRAY, font=self.fonts["tiny"])
        else:
            draw.text((310, 80), "--", fill=GRAY, font=self.fonts["large"])

        # Event timeline at bottom
        y_timeline = 185
        draw.line([(15, y_timeline + 15), (295, y_timeline + 15)], fill=DARK_GRAY, width=2)

        if sun_times:
            events_list = [
                ("dawn", "Dawn", LIGHT_BLUE),
                ("sunrise", "Rise", YELLOW),
                ("noon", "Noon", WHITE),
                ("sunset", "Set", ORANGE),
                ("dusk", "Dusk", PURPLE),
            ]

            x_positions = [30, 85, 155, 210, 265]

            for i, (key, label, color) in enumerate(events_list):
                event_time = sun_times.get(key)
                x = x_positions[i]

                if event_time:
                    # Check if this event has passed
                    passed = event_time <= now
                    display_color = DARK_GRAY if passed else color

                    # Marker dot
                    draw.ellipse([(x-4, y_timeline + 11), (x+4, y_timeline + 19)],
                               fill=display_color)

                    # Time
                    time_str = event_time.strftime("%H:%M")
                    draw.text((x - 15, y_timeline + 22), time_str,
                             fill=display_color, font=self.fonts["micro"])

                    # Label
                    draw.text((x - 12, y_timeline - 2), label,
                             fill=display_color, font=self.fonts["micro"])

        # Current elevation/azimuth
        if elev is not None:
            status = "Up" if elev > 0 else "Down"
            draw.text((310, 175), f"Elev: {elev:.1f} ({status})",
                     fill=YELLOW if elev > 0 else GRAY, font=self.fonts["tiny"])
            draw.text((310, 192), f"Azim: {azim:.1f}",
                     fill=WHITE, font=self.fonts["tiny"])

        # Draw time on chart
        draw.text((310, 215), now.strftime("%I:%M %p"),
                 fill=GRAY, font=self.fonts["small"])

        # Navigation bar
        self.draw_nav_bar(draw)

        return img

    def create_weather_frame(self):
        """Weather forecast view - improved readability"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 40)], fill=BLUE)
        draw.text((WIDTH//2 - 50, 5), "Weather", fill=WHITE, font=self.fonts["large"])

        forecast = self.get_weather_forecast()

        # Current conditions section
        if forecast and 'current_condition' in forecast:
            cc = forecast['current_condition'][0]
            temp = cc.get('temp_F', '--')
            feels = cc.get('FeelsLikeF', '--')
            humidity = cc.get('humidity', '--')
            wind_speed = cc.get('windspeedMiles', '--')
            wind_dir = cc.get('winddir16Point', '')
            desc = cc.get('weatherDesc', [{}])[0].get('value', '')[:18]

            # Large temperature
            draw.text((20, 45), f"{temp}", fill=WHITE, font=self.fonts["huge"])
            draw.text((95, 55), "F", fill=GRAY, font=self.fonts["large"])

            # Description
            draw.text((20, 100), desc, fill=LIGHT_BLUE, font=self.fonts["small"])

            # Details on right side
            draw.text((150, 48), f"Feels {feels}F", fill=GRAY, font=self.fonts["small"])
            draw.text((150, 68), f"Humidity {humidity}%", fill=LIGHT_BLUE, font=self.fonts["small"])
            draw.text((150, 88), f"Wind {wind_speed}mph {wind_dir}", fill=GRAY, font=self.fonts["small"])

        # Divider
        draw.line([(15, 122), (465, 122)], fill=DARK_GRAY, width=1)

        # 3-day forecast
        if forecast and 'weather' in forecast:
            # Calculate card width for 3 cards with spacing
            card_width = 150
            card_height = 125
            spacing = 8
            start_x = 10
            y = 128

            for i, day in enumerate(forecast['weather'][:3]):
                x = start_x + i * (card_width + spacing)

                date = day.get('date', '')
                max_temp = day.get('maxtempF', '--')
                min_temp = day.get('mintempF', '--')

                # Get rain chance and description
                rain_chance = '0'
                desc = ''
                if 'hourly' in day and len(day['hourly']) > 4:
                    h = day['hourly'][4]
                    rain_chance = h.get('chanceofrain', '0')
                    desc = h.get('weatherDesc', [{}])[0].get('value', '')[:12]

                # Day name
                try:
                    dt = datetime.datetime.strptime(date, "%Y-%m-%d")
                    if i == 0:
                        day_name = "Today"
                    elif i == 1:
                        day_name = "Tomorrow"
                    else:
                        day_name = dt.strftime("%A")[:3]
                except:
                    day_name = f"Day {i+1}"

                # Card background
                draw.rounded_rectangle([(x, y), (x + card_width, y + card_height)],
                                      radius=8, fill=DARK_GRAY)

                # Day name header
                draw.text((x + 10, y + 5), day_name, fill=WHITE, font=self.fonts["med"])

                # High/Low temps - large and clear
                draw.text((x + 10, y + 32), f"{max_temp}", fill=ORANGE, font=self.fonts["large"])
                draw.text((x + 55, y + 38), f"/{min_temp}", fill=LIGHT_BLUE, font=self.fonts["med"])

                # Rain chance
                rain_color = LIGHT_BLUE if int(rain_chance) > 30 else GRAY
                draw.text((x + 10, y + 70), f"Rain {rain_chance}%", fill=rain_color, font=self.fonts["tiny"])

                # Description
                draw.text((x + 10, y + 88), desc, fill=GRAY, font=self.fonts["tiny"])

        else:
            draw.text((20, 140), "Forecast unavailable", fill=GRAY, font=self.fonts["med"])

        # Navigation bar
        self.draw_nav_bar(draw)

        return img

    def create_moon_frame(self):
        """Moon phase view"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 45)], fill=PURPLE)
        draw.text((WIDTH//2 - 65, 8), "Moon Phase", fill=WHITE, font=self.fonts["large"])

        content_bottom = HEIGHT - NAV_BAR_HEIGHT - 5
        moon = self.get_moon_phase()

        if moon:
            # Draw large moon - centered vertically in content area
            moon_cy = 140
            self.draw_moon(draw, 110, moon_cy, 55, moon['phase'])

            # Moon info on right side
            draw.text((200, 60), moon['phase_name'], fill=MOON_YELLOW, font=self.fonts["large"])
            draw.text((200, 98), f"Illumination: {moon['illumination']:.1f}%",
                     fill=WHITE, font=self.fonts["med"])

            # Next new moon
            next_new = moon['next_new']
            new_str = next_new.strftime("%b %d")
            days_to_new = (next_new.date() - datetime.date.today()).days
            draw.text((200, 135), f"New Moon: {new_str}", fill=GRAY, font=self.fonts["small"])
            draw.text((200, 155), f"({days_to_new} days)", fill=DARK_GRAY, font=self.fonts["tiny"])

            # Next full moon
            next_full = moon['next_full']
            full_str = next_full.strftime("%b %d")
            days_to_full = (next_full.date() - datetime.date.today()).days
            draw.text((200, 180), f"Full Moon: {full_str}", fill=GRAY, font=self.fonts["small"])
            draw.text((200, 200), f"({days_to_full} days)", fill=DARK_GRAY, font=self.fonts["tiny"])

            # Moon rise/set if available
            draw.text((200, 230), "Swipe or tap arrows", fill=DARK_GRAY, font=self.fonts["tiny"])
        else:
            draw.text((WIDTH//2 - 100, 120), "Moon data unavailable",
                     fill=GRAY, font=self.fonts["med"])
            draw.text((WIDTH//2 - 80, 150), "(install ephem library)",
                     fill=DARK_GRAY, font=self.fonts["small"])

        # Navigation bar
        self.draw_nav_bar(draw)

        return img

    def create_solar_frame(self):
        """Detailed solar information view"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 45)], fill=ORANGE)
        draw.text((WIDTH//2 - 70, 8), "Solar Details", fill=WHITE, font=self.fonts["large"])

        sun_times = self.get_sun_times()
        elev, azim = self.get_solar_position()

        content_bottom = HEIGHT - NAV_BAR_HEIGHT - 5
        y = 52

        if sun_times:
            # Dawn/Dusk
            dawn = sun_times.get("dawn")
            dusk = sun_times.get("dusk")
            if dawn and dusk:
                draw.text((15, y), f"Dawn: {dawn.strftime('%I:%M %p')}",
                         fill=LIGHT_BLUE, font=self.fonts["small"])
                draw.text((250, y), f"Dusk: {dusk.strftime('%I:%M %p')}",
                         fill=PURPLE, font=self.fonts["small"])
                y += 22

            # Sunrise/Sunset
            sunrise = sun_times.get("sunrise")
            sunset = sun_times.get("sunset")
            if sunrise and sunset:
                draw.text((15, y), f"Sunrise: {sunrise.strftime('%I:%M %p')}",
                         fill=YELLOW, font=self.fonts["small"])
                draw.text((250, y), f"Sunset: {sunset.strftime('%I:%M %p')}",
                         fill=ORANGE, font=self.fonts["small"])
                y += 22

            # Solar noon and day length
            noon = sun_times.get("noon")
            if noon and sunrise and sunset:
                draw.text((15, y), f"Solar Noon: {noon.strftime('%I:%M %p')}",
                         fill=WHITE, font=self.fonts["small"])
                day_len = sunset - sunrise
                hours = int(day_len.total_seconds() // 3600)
                mins = int((day_len.total_seconds() % 3600) // 60)
                draw.text((250, y), f"Day: {hours}h {mins}m",
                         fill=GRAY, font=self.fonts["small"])
                y += 22

        # Separator
        y += 5
        draw.line([(15, y), (465, y)], fill=DARK_GRAY, width=1)
        y += 8

        # Golden hour section
        draw.text((15, y), "Golden Hour", fill=YELLOW, font=self.fonts["small"])
        y += 20

        morning_gh, evening_gh = self.get_golden_hour()
        if morning_gh:
            draw.text((15, y), f"AM: {morning_gh[0].strftime('%I:%M')}-{morning_gh[1].strftime('%I:%M')}",
                     fill=ORANGE, font=self.fonts["tiny"])
        else:
            draw.text((15, y), "AM: --", fill=GRAY, font=self.fonts["tiny"])

        if evening_gh:
            draw.text((150, y), f"PM: {evening_gh[0].strftime('%I:%M')}-{evening_gh[1].strftime('%I:%M')}",
                     fill=ORANGE, font=self.fonts["tiny"])
        else:
            draw.text((150, y), "PM: --", fill=GRAY, font=self.fonts["tiny"])
        y += 20

        # Separator
        y += 3
        draw.line([(15, y), (465, y)], fill=DARK_GRAY, width=1)
        y += 8

        # Current position
        draw.text((15, y), "Current Position", fill=WHITE, font=self.fonts["small"])
        y += 20

        if elev is not None:
            status = "Above" if elev > 0 else "Below"
            draw.text((15, y), f"Elevation: {elev:.1f} ({status})",
                     fill=YELLOW if elev > 0 else GRAY, font=self.fonts["tiny"])
            draw.text((200, y), f"Azimuth: {azim:.1f}",
                     fill=WHITE, font=self.fonts["tiny"])
            y += 18

            # Direction hint
            if azim < 90:
                direction = "NE"
            elif azim < 180:
                direction = "SE"
            elif azim < 270:
                direction = "SW"
            else:
                direction = "NW"
            draw.text((15, y), f"Direction: {direction}", fill=GRAY, font=self.fonts["tiny"])

        # Navigation bar
        self.draw_nav_bar(draw)

        return img

    def create_frame(self):
        """Create current view frame"""
        view = self.view_manager.get_current()

        if view == "clock":
            return self.create_clock_frame()
        elif view == "sunpath":
            return self.create_sunpath_frame()
        elif view == "weather":
            return self.create_weather_frame()
        elif view == "moon":
            return self.create_moon_frame()
        elif view == "solar":
            return self.create_solar_frame()
        else:
            return self.create_clock_frame()

    def write_fb(self, img):
        px = list(img.convert("RGB").getdata())
        fb = bytearray(WIDTH * HEIGHT * 2)
        for i, (r, g, b) in enumerate(px):
            c = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            fb[i*2] = c & 0xFF
            fb[i*2+1] = (c >> 8) & 0xFF
        with open(self.fb_device, "wb") as f:
            f.write(fb)

    def run(self):
        print(f"Solar Clock running ({WIDTH}x{HEIGHT})")
        print(f"Views: {ViewManager.VIEWS}")
        print("Navigation: Swipe left/right or tap < > buttons")

        self.touch_handler.start()

        try:
            while True:
                self.write_fb(self.create_frame())
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.touch_handler.stop()

if __name__ == "__main__":
    SolarClock().run()
