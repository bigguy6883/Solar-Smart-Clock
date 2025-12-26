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
# OpenWeatherMap API (free tier) for Air Quality
OPENWEATHER_API_KEY = "ac5189e6a0f50737d3145e449c96c5e6"


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

# Air Quality Index colors
AQI_GOOD = (0, 228, 0)
AQI_MODERATE = (255, 255, 0)
AQI_UNHEALTHY_SENSITIVE = (255, 126, 0)
AQI_UNHEALTHY = (255, 0, 0)
AQI_VERY_UNHEALTHY = (143, 63, 151)
AQI_HAZARDOUS = (126, 0, 35)


class ViewManager:
    """Manages navigation between views"""
    VIEWS = ["clock", "sunpath", "weather", "moon", "solar", "airquality", "daylength", "analemma"]

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
                self.view_manager.prev_view()  # Swipe right = prev
                if self.debug: print(f"SWIPE RIGHT -> {self.view_manager.get_current()}", flush=True)
            else:
                self.view_manager.next_view()  # Swipe left = next
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
        time_str = now.strftime("%-I:%M:%S %p")
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
                ("noon", "Noon", WHITE),
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
        """Sun path view - chart across top"""
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(LOCATION.timezone)
        now = datetime.datetime.now(tz)

        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        sun_times = self.get_sun_times()
        elev, azim = self.get_solar_position()

        # Header
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=ORANGE)
        title = "Sun Path"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 6), title, fill=WHITE, font=self.fonts["large"])

        # SUN ARC CHART - Full width across top
        chart_cx = WIDTH // 2
        chart_cy = 115
        chart_radius = 65
        
        # Chart background box
        draw.rounded_rectangle([(10, 47), (WIDTH - 10, 150)], radius=8, fill=(15, 15, 25))
        
        # Horizon line - full width
        horizon_y = 130
        draw.line([(30, horizon_y), (WIDTH - 30, horizon_y)], fill=GRAY, width=2)
        
        # Twilight zone line (below horizon)
        twilight_y = horizon_y + 12
        draw.line([(30, twilight_y), (WIDTH - 30, twilight_y)], fill=(40, 40, 60), width=1)
        
        # E and W labels
        draw.text((15, horizon_y - 10), "E", fill=WHITE, font=self.fonts["small"])
        draw.text((WIDTH - 28, horizon_y - 10), "W", fill=WHITE, font=self.fonts["small"])

        # Sun path arc for today
        if sun_times:
            sunrise = sun_times.get("sunrise")
            sunset = sun_times.get("sunset")
            noon = sun_times.get("noon")

            if sunrise and sunset and noon:
                path_points = []
                for mins_offset in range(-360, 361, 10):
                    check_time = noon + datetime.timedelta(minutes=mins_offset)
                    if sunrise <= check_time <= sunset:
                        try:
                            check_utc = check_time.astimezone(datetime.timezone.utc)
                            e = elevation(LOCATION.observer, check_utc)
                            a = azimuth(LOCATION.observer, check_utc)
                            if e >= 0:
                                # Map azimuth to x position (full width)
                                # Typical range: ~60-300 degrees
                                norm_x = (a - 60) / 240
                                x = 40 + int(norm_x * (WIDTH - 80))
                                # Map elevation to y
                                y = horizon_y - int((e / 90) * chart_radius)
                                path_points.append((x, y))
                        except:
                            pass


                # Draw path
                if len(path_points) > 1:
                    for i in range(len(path_points) - 1):
                        draw.line([path_points[i], path_points[i+1]], fill=RED, width=3)

                # Solar noon marker
                if noon:
                    try:
                        noon_utc = noon.astimezone(datetime.timezone.utc)
                        noon_elev = elevation(LOCATION.observer, noon_utc)
                        noon_az = azimuth(LOCATION.observer, noon_utc)
                        norm_x = (noon_az - 60) / 240
                        nx = 40 + int(norm_x * (WIDTH - 80))
                        ny = horizon_y - int((noon_elev / 90) * chart_radius)
                        draw.ellipse([(nx-5, ny-5), (nx+5, ny+5)], fill=WHITE)
                    except:
                        pass

        # Current sun position
        if elev is not None and azim is not None and elev > -18:  # Show during twilight
            norm_x = (azim - 60) / 240
            x = 40 + int(norm_x * (WIDTH - 80))
            y = horizon_y - int((elev / 90) * chart_radius)  # Negative elev goes below horizon
            draw.ellipse([(x-10, y-10), (x+10, y+10)], fill=ORANGE)
            draw.ellipse([(x-6, y-6), (x+6, y+6)], fill=YELLOW)

        # BOTTOM SECTION - Countdown and event times
        
        # Next event countdown - left side
        next_event, time_delta, event_color = self.get_next_solar_event()
        
        draw.rounded_rectangle([(10, 152), (200, 235)], radius=8, fill=(25, 25, 35), outline=(60, 60, 80), width=1)
        
        if next_event and time_delta:
            evt_name = next_event.lower().replace(" (tomorrow)", "")
            draw.text((20, 158), evt_name, fill=event_color or ORANGE, font=self.fonts["med"])
            
            total_secs = int(time_delta.total_seconds())
            hours = total_secs // 3600
            mins = (total_secs % 3600) // 60
            
            draw.text((20, 182), "in", fill=GRAY, font=self.fonts["small"])
            draw.text((50, 178), f"{hours:02d}", fill=YELLOW, font=self.fonts["large"])
            draw.text((95, 185), "h", fill=GRAY, font=self.fonts["small"])
            draw.text((115, 178), f"{mins:02d}", fill=YELLOW, font=self.fonts["large"])
            draw.text((160, 185), "m", fill=GRAY, font=self.fonts["small"])
            
            # Event time
            for key in ["dawn", "sunrise", "noon", "sunset", "dusk"]:
                if key in next_event.lower():
                    evt_time = sun_times.get(key) if sun_times else None
                    if evt_time:
                        draw.text((20, 212), "@", fill=GRAY, font=self.fonts["small"])
                        draw.text((40, 212), evt_time.strftime("%-I:%M %p"), fill=YELLOW, font=self.fonts["small"])
                    break
        else:
            draw.text((20, 180), "--", fill=GRAY, font=self.fonts["large"])

        # Event times - right side box
        draw.rounded_rectangle([(210, 152), (WIDTH - 10, 235)], radius=8, fill=(25, 25, 35), outline=(60, 60, 80), width=1)
        draw.text((220, 158), "Today's Events", fill=GRAY, font=self.fonts["small"])
        
        if sun_times:
            events = [
                ("dawn", "Dawn", LIGHT_BLUE),
                ("sunrise", "Sunrise", YELLOW),
                ("sunset", "Sunset", ORANGE),
                ("dusk", "Dusk", PURPLE),
            ]
            
            y_pos = 178
            for key, label, color in events:
                evt_time = sun_times.get(key)
                if evt_time:
                    passed = evt_time <= now
                    disp_color = (70, 70, 70) if passed else color
                    draw.text((220, y_pos), label, fill=disp_color, font=self.fonts["tiny"])
                    draw.text((280, y_pos), evt_time.strftime("%-I:%M %p"), fill=disp_color, font=self.fonts["tiny"])
                    y_pos += 14

        self.draw_nav_bar(draw)
        return img

    def create_weather_frame(self):
        """Weather forecast view"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=BLUE)
        title = "Weather"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 6), title, fill=WHITE, font=self.fonts["large"])

        forecast = self.get_weather_forecast()

        # LEFT SIDE - Current conditions
        if forecast and 'current_condition' in forecast:
            cc = forecast['current_condition'][0]
            temp = cc.get('temp_F', '--')
            feels = cc.get('FeelsLikeF', '--')
            humidity = cc.get('humidity', '--')
            desc = cc.get('weatherDesc', [{}])[0].get('value', '')[:18]
            wind_speed = cc.get('windspeedMiles', '0')
            wind_dir = cc.get('winddir16Point', 'N')

            # Current box
            draw.rounded_rectangle([(8, 48), (190, 165)], radius=8, fill=(25, 25, 35), outline=(70, 70, 90), width=1)
            
            draw.text((18, 55), f"{temp}°F", fill=WHITE, font=self.fonts["huge"])
            draw.text((18, 110), desc, fill=LIGHT_BLUE, font=self.fonts["small"])
            draw.text((18, 132), f"Feels {feels}° | {humidity}%", fill=GRAY, font=self.fonts["tiny"])
            draw.text((18, 148), f"Wind {wind_speed}mph {wind_dir}", fill=GRAY, font=self.fonts["tiny"])

            # Compass box
            draw.rounded_rectangle([(8, 172), (190, 235)], radius=8, fill=(25, 25, 35), outline=(70, 70, 90), width=1)
            
            compass_cx = 50
            compass_cy = 203
            compass_r = 22
            
            draw.ellipse([(compass_cx - compass_r, compass_cy - compass_r),
                         (compass_cx + compass_r, compass_cy + compass_r)], outline=WHITE, width=1)
            
            draw.text((compass_cx - 3, compass_cy - compass_r - 10), "N", fill=WHITE, font=self.fonts["micro"])
            draw.text((compass_cx - 3, compass_cy + compass_r + 2), "S", fill=WHITE, font=self.fonts["micro"])
            draw.text((compass_cx - compass_r - 8, compass_cy - 4), "W", fill=WHITE, font=self.fonts["micro"])
            draw.text((compass_cx + compass_r + 3, compass_cy - 4), "E", fill=WHITE, font=self.fonts["micro"])
            
            dir_angles = {
                'N': 270, 'NNE': 292, 'NE': 315, 'ENE': 337,
                'E': 0, 'ESE': 22, 'SE': 45, 'SSE': 67,
                'S': 90, 'SSW': 112, 'SW': 135, 'WSW': 157,
                'W': 180, 'WNW': 202, 'NW': 225, 'NNW': 247
            }
            import math
            angle_deg = dir_angles.get(wind_dir, 0)
            angle_rad = math.radians(angle_deg)
            ax = compass_cx + int(18 * math.cos(angle_rad))
            ay = compass_cy + int(18 * math.sin(angle_rad))
            draw.line([(compass_cx, compass_cy), (ax, ay)], fill=YELLOW, width=3)
            draw.ellipse([(ax - 3, ay - 3), (ax + 3, ay + 3)], fill=YELLOW)
            
            draw.text((90, 188), "Wind", fill=GRAY, font=self.fonts["tiny"])
            draw.text((90, 202), f"{wind_speed}", fill=WHITE, font=self.fonts["large"])
            draw.text((140, 210), "mph", fill=GRAY, font=self.fonts["tiny"])

        draw.text((15, 245), f"{LOCATION.name}", fill=GRAY, font=self.fonts["tiny"])

        # RIGHT SIDE - Forecast table (x: 200 to 470, width=270)
        if forecast and 'weather' in forecast:
            x = 200
            
            # Column positions spread evenly across 270px
            col_day = x + 8
            col_high = x + 100
            col_low = x + 165
            col_rain = x + 230
            
            y = 52
            
            # Headers
            draw.text((col_day, y), "Day", fill=GRAY, font=self.fonts["tiny"])
            draw.text((col_high, y), "High", fill=GRAY, font=self.fonts["tiny"])
            draw.text((col_low, y), "Low", fill=GRAY, font=self.fonts["tiny"])
            draw.text((col_rain, y), "Rain", fill=GRAY, font=self.fonts["tiny"])
            
            y += 18
            draw.line([(x, y), (WIDTH - 10, y)], fill=GRAY, width=1)
            y += 8

            for i, day in enumerate(forecast['weather'][:3]):
                date = day.get('date', '')
                max_temp = day.get('maxtempF', '--')
                min_temp = day.get('mintempF', '--')

                rain_chance = '0'
                if 'hourly' in day and len(day['hourly']) > 4:
                    rain_chance = day['hourly'][4].get('chanceofrain', '0')

                try:
                    dt = datetime.datetime.strptime(date, "%Y-%m-%d")
                    if i == 0:
                        day_name = "Today"
                    elif i == 1:
                        day_name = "Tmrw"
                    else:
                        day_name = dt.strftime("%a")
                except:
                    day_name = "--"

                row_y = y + i * 55
                
                # Row background
                draw.rounded_rectangle([(x, row_y), (WIDTH - 10, row_y + 48)], 
                                      radius=6, fill=(20, 20, 30))

                # Day name
                draw.text((col_day, row_y + 14), day_name, fill=WHITE, font=self.fonts["med"])

                # High temp
                draw.text((col_high, row_y + 14), max_temp + "°", fill=(255, 180, 50), font=self.fonts["med"])

                # Low temp
                draw.text((col_low, row_y + 14), min_temp + "°", fill=(100, 180, 255), font=self.fonts["med"])

                # Rain %
                rain_val = int(rain_chance) if rain_chance.isdigit() else 0
                if rain_val > 50:
                    rain_color = (100, 200, 255)
                elif rain_val > 20:
                    rain_color = (150, 180, 200)
                else:
                    rain_color = GRAY
                draw.text((col_rain, row_y + 14), f"{rain_chance}%", fill=rain_color, font=self.fonts["med"])

        self.draw_nav_bar(draw)
        return img

    def create_moon_frame(self):
        """Moon phase view"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 45)], fill=PURPLE)
        title = "Moon Phase"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 8), title, fill=WHITE, font=self.fonts["large"])

        content_bottom = HEIGHT - NAV_BAR_HEIGHT - 5
        moon = self.get_moon_phase()

        if moon:
            # Draw large moon - centered vertically in content area
            moon_cy = 140
            self.draw_moon(draw, 110, moon_cy, 55, moon['phase'])

            # Moon info on right side
            draw.text((185, 60), moon['phase_name'], fill=MOON_YELLOW, font=self.fonts["med"])
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
        title = "Solar Details"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 8), title, fill=WHITE, font=self.fonts["large"])

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


    def get_air_quality(self):
        """Fetch air quality data from OpenWeatherMap"""
        now = time.time()
        if hasattr(self, 'aqi_data') and self.aqi_data and (now - self.aqi_last_update) < 1800:
            return self.aqi_data
        
        try:
            url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={LOCATION.latitude}&lon={LOCATION.longitude}&appid={OPENWEATHER_API_KEY}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                self.aqi_data = data
                self.aqi_last_update = now
                return data
        except Exception as e:
            print(f"AQI fetch error: {e}", flush=True)
        
        if not hasattr(self, 'aqi_data'):
            self.aqi_data = None
            self.aqi_last_update = 0
        return self.aqi_data

    def get_aqi_color(self, aqi):
        """Get color for AQI level (1-5 scale from OpenWeatherMap)"""
        colors = {
            1: AQI_GOOD,
            2: AQI_MODERATE,
            3: AQI_UNHEALTHY_SENSITIVE,
            4: AQI_UNHEALTHY,
            5: AQI_VERY_UNHEALTHY
        }
        return colors.get(aqi, GRAY)

    def get_aqi_label(self, aqi):
        """Get label for AQI level"""
        labels = {
            1: "Good",
            2: "Fair",
            3: "Moderate",
            4: "Poor",
            5: "Very Poor"
        }
        return labels.get(aqi, "Unknown")

    def create_airquality_frame(self):
        """Air quality view with AQI and pollutants"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        aqi_data = self.get_air_quality()
        
        if aqi_data and 'list' in aqi_data and len(aqi_data['list']) > 0:
            aqi_info = aqi_data['list'][0]
            aqi = aqi_info['main']['aqi']
            components = aqi_info['components']
            aqi_color = self.get_aqi_color(aqi)
            aqi_label = self.get_aqi_label(aqi)
        else:
            aqi = 0
            components = {}
            aqi_color = GRAY
            aqi_label = "Waiting..."

        # Header with AQI color
        draw.rectangle([(0, 0), (WIDTH, 45)], fill=aqi_color if aqi > 0 else DARK_GRAY)
        header_text = "Air Quality"
        bbox = draw.textbbox((0, 0), header_text, font=self.fonts["large"])
        tw = bbox[2] - bbox[0]
        text_color = BLACK if aqi in [1, 2] else WHITE
        draw.text((WIDTH//2 - tw//2, 8), header_text, fill=text_color, font=self.fonts["large"])

        # Left side: Large AQI display
        aqi_y = 55
        draw.text((25, aqi_y), "AQI Level", fill=GRAY, font=self.fonts["small"])
        aqi_str = str(aqi) if aqi > 0 else "--"
        draw.text((25, aqi_y + 25), aqi_str, fill=aqi_color, font=self.fonts["huge"])
        draw.text((25, aqi_y + 85), aqi_label, fill=aqi_color, font=self.fonts["large"])

        # Right side: Pollutants - wider layout
        poll_x = 160
        poll_y = 55
        bar_width = 155  # Wider bars
        
        draw.text((poll_x, poll_y), "Pollutants", fill=WHITE, font=self.fonts["med"])
        
        pollutants = [
            ("PM2.5", components.get('pm2_5', 0), 75, "ug/m3"),
            ("PM10", components.get('pm10', 0), 150, "ug/m3"),
            ("O3", components.get('o3', 0), 180, "ug/m3"),
            ("NO2", components.get('no2', 0), 200, "ug/m3"),
            ("CO", components.get('co', 0) / 100, 100, "mg/m3"),
        ]
        
        bar_y = poll_y + 28
        bar_height = 20
        
        for name, value, max_val, unit in pollutants:
            # Label
            draw.text((poll_x, bar_y + 2), name, fill=WHITE, font=self.fonts["small"])
            # Bar background
            bar_x = poll_x + 75
            draw.rectangle([(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)], fill=DARK_GRAY)
            # Bar fill
            if max_val > 0:
                fill_width = min(int((value / max_val) * bar_width), bar_width)
                if fill_width > 0:
                    ratio = value / max_val
                    bar_color = AQI_GOOD if ratio < 0.5 else (AQI_MODERATE if ratio < 0.75 else AQI_UNHEALTHY)
                    draw.rectangle([(bar_x, bar_y), (bar_x + fill_width, bar_y + bar_height)], fill=bar_color)
            # Value on bar
            val_text = f"{value:.1f}"
            draw.text((bar_x + 5, bar_y + 2), val_text, fill=WHITE, font=self.fonts["small"])
            bar_y += 28

        # Bottom info
        info_y = HEIGHT - NAV_BAR_HEIGHT - 40
        draw.text((25, info_y), f"{LOCATION.name}", fill=GRAY, font=self.fonts["small"])
        if aqi == 0:
            draw.text((200, info_y), "API key activating...", fill=ORANGE, font=self.fonts["small"])
        elif hasattr(self, 'aqi_last_update') and self.aqi_last_update > 0:
            update_time = datetime.datetime.fromtimestamp(self.aqi_last_update).strftime("%I:%M %p")
            draw.text((200, info_y), f"Updated {update_time}", fill=GRAY, font=self.fonts["small"])

        self.draw_nav_bar(draw)
        return img

    def calculate_day_length(self, date):
        """Calculate day length for a specific date"""
        try:
            s = sun(LOCATION.observer, date=date, tzinfo=LOCATION.timezone)
            sunrise = s['sunrise']
            sunset = s['sunset']
            day_length = (sunset - sunrise).total_seconds() / 3600
            return day_length
        except:
            return 12.0  # Default to 12 hours if calculation fails

    def create_daylength_frame(self):
        """Day length chart for full year"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=YELLOW)
        title = "Day Length"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 6), title, fill=BLACK, font=self.fonts["large"])

        # Chart area
        chart_left = 45
        chart_right = WIDTH - 15
        chart_top = 55
        chart_bottom = HEIGHT - NAV_BAR_HEIGHT - 35
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top

        # Calculate day lengths for the year
        today = datetime.date.today()
        year = today.year
        day_lengths = []
        
        for day_of_year in range(1, 366):
            try:
                date = datetime.date(year, 1, 1) + datetime.timedelta(days=day_of_year - 1)
                dl = self.calculate_day_length(date)
                day_lengths.append((day_of_year, dl, date))
            except:
                pass

        if not day_lengths:
            draw.text((100, 150), "No data available", fill=GRAY, font=self.fonts["med"])
            self.draw_nav_bar(draw)
            return img

        # Find min/max for scaling
        min_dl = min(dl for _, dl, _ in day_lengths)
        max_dl = max(dl for _, dl, _ in day_lengths)
        dl_range = max_dl - min_dl

        # Draw Y axis labels (hours)
        for hours in range(int(min_dl), int(max_dl) + 2, 2):
            if min_dl <= hours <= max_dl:
                y = chart_bottom - int((hours - min_dl) / dl_range * chart_height)
                draw.text((5, y - 7), f"{hours}h", fill=GRAY, font=self.fonts["micro"])
                draw.line([(chart_left, y), (chart_right, y)], fill=DARK_GRAY, width=1)

        # Draw X axis labels (months)
        months = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
        for i, m in enumerate(months):
            x = chart_left + int((i + 0.5) * chart_width / 12)
            draw.text((x - 4, chart_bottom + 5), m, fill=GRAY, font=self.fonts["micro"])

        # Draw day length curve
        points = []
        for day_of_year, dl, date in day_lengths:
            x = chart_left + int((day_of_year - 1) / 365 * chart_width)
            y = chart_bottom - int((dl - min_dl) / dl_range * chart_height)
            points.append((x, y))

        # Draw curve
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=ORANGE, width=2)

        # Mark solstices and equinoxes
        special_days = [
            (80, "Spring", LIGHT_BLUE),   # ~Mar 20
            (172, "Summer", YELLOW),       # ~Jun 21
            (266, "Fall", ORANGE),         # ~Sep 22
            (355, "Winter", BLUE),         # ~Dec 21
        ]
        
        for day_num, label, color in special_days:
            if day_num <= len(day_lengths):
                x = chart_left + int((day_num - 1) / 365 * chart_width)
                draw.line([(x, chart_top), (x, chart_bottom)], fill=color, width=1)

        # Mark today
        today_day = today.timetuple().tm_yday
        today_dl = self.calculate_day_length(today)
        today_x = chart_left + int((today_day - 1) / 365 * chart_width)
        today_y = chart_bottom - int((today_dl - min_dl) / dl_range * chart_height)
        
        draw.ellipse([(today_x - 5, today_y - 5), (today_x + 5, today_y + 5)], fill=WHITE, outline=YELLOW)

        # Today's info
        hours = int(today_dl)
        mins = int((today_dl - hours) * 60)
        draw.text((chart_left, chart_bottom + 18), f"Today: {hours}h {mins}m", fill=WHITE, font=self.fonts["small"])

        self.draw_nav_bar(draw)
        return img

    def calculate_analemma_point(self, date):
        """Calculate analemma point for a date (equation of time and declination)"""
        if not EPHEM_AVAILABLE:
            return None, None
        
        try:
            obs = ephem.Observer()
            obs.lat = str(LOCATION.latitude)
            obs.lon = str(LOCATION.longitude)
            obs.date = date.strftime('%Y/%m/%d 12:00:00')  # Solar noon
            
            s = ephem.Sun()
            s.compute(obs)
            
            # Declination in degrees
            decl = math.degrees(float(s.dec))
            
            # Equation of time (difference between solar and clock noon)
            # Approximate using the sun's right ascension
            ra = math.degrees(float(s.ra))
            # Convert to hour angle offset (simplified equation of time)
            day_of_year = date.timetuple().tm_yday
            B = 2 * math.pi * (day_of_year - 81) / 365
            eot = 9.87 * math.sin(2 * B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)
            
            return eot, decl
        except:
            return None, None

    def create_analemma_frame(self):
        """Analemma chart showing sun position at noon throughout year"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=ORANGE)
        title = "Analemma"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 6), title, fill=BLACK, font=self.fonts["large"])

        if not EPHEM_AVAILABLE:
            draw.text((100, 150), "ephem library required", fill=GRAY, font=self.fonts["med"])
            self.draw_nav_bar(draw)
            return img

        # Chart area
        chart_cx = WIDTH // 2
        chart_cy = (HEIGHT - NAV_BAR_HEIGHT + 42) // 2
        
        # Scale: EoT is typically -15 to +15 minutes, declination -23.5 to +23.5 degrees
        eot_scale = 8  # pixels per minute
        decl_scale = 4  # pixels per degree

        # Draw axes
        # Vertical axis (declination)
        draw.line([(chart_cx, 50), (chart_cx, HEIGHT - NAV_BAR_HEIGHT - 10)], fill=DARK_GRAY, width=1)
        # Horizontal axis (equation of time)
        draw.line([(50, chart_cy), (WIDTH - 50, chart_cy)], fill=DARK_GRAY, width=1)

        # Axis labels
        draw.text((chart_cx + 5, 48), "+23.5", fill=GRAY, font=self.fonts["micro"])
        draw.text((chart_cx + 5, HEIGHT - NAV_BAR_HEIGHT - 20), "-23.5", fill=GRAY, font=self.fonts["micro"])
        draw.text((55, chart_cy - 15), "-15m", fill=GRAY, font=self.fonts["micro"])
        draw.text((WIDTH - 85, chart_cy - 15), "+15m", fill=GRAY, font=self.fonts["micro"])

        # Calculate analemma points for the year
        today = datetime.date.today()
        year = today.year
        points = []
        month_points = {}
        
        for day_of_year in range(1, 366, 3):  # Every 3 days for smoother curve
            try:
                date = datetime.date(year, 1, 1) + datetime.timedelta(days=day_of_year - 1)
                eot, decl = self.calculate_analemma_point(date)
                if eot is not None:
                    x = chart_cx + int(eot * eot_scale)
                    y = chart_cy - int(decl * decl_scale)
                    points.append((x, y, date))
                    
                    # Store first point of each month for labeling
                    if date.day <= 3 and date.month not in month_points:
                        month_points[date.month] = (x, y)
            except:
                pass

        # Draw analemma curve
        if len(points) > 1:
            for i in range(len(points) - 1):
                draw.line([(points[i][0], points[i][1]), (points[i + 1][0], points[i + 1][1])], fill=YELLOW, width=2)

        # Draw month markers
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        for month, (x, y) in month_points.items():
            draw.ellipse([(x - 4, y - 4), (x + 4, y + 4)], fill=WHITE)
            # Position label to avoid overlap
            label_x = x + 8 if x < chart_cx else x - 25
            draw.text((label_x, y - 6), month_names[month - 1], fill=LIGHT_BLUE, font=self.fonts["micro"])

        # Mark today's position
        today_eot, today_decl = self.calculate_analemma_point(today)
        if today_eot is not None:
            today_x = chart_cx + int(today_eot * eot_scale)
            today_y = chart_cy - int(today_decl * decl_scale)
            draw.ellipse([(today_x - 6, today_y - 6), (today_x + 6, today_y + 6)], fill=ORANGE)
            draw.ellipse([(today_x - 4, today_y - 4), (today_x + 4, today_y + 4)], fill=YELLOW)

        # Info at bottom
        if today_eot is not None:
            info_y = HEIGHT - NAV_BAR_HEIGHT - 25
            eot_str = f"+{today_eot:.1f}" if today_eot >= 0 else f"{today_eot:.1f}"
            draw.text((20, info_y), f"Today: EoT {eot_str}min  Decl {today_decl:.1f}", fill=WHITE, font=self.fonts["tiny"])

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
        elif view == "airquality":
            return self.create_airquality_frame()
        elif view == "daylength":
            return self.create_daylength_frame()
        elif view == "analemma":
            return self.create_analemma_frame()
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
