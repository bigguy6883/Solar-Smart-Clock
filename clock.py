#!/usr/bin/env python3
"""Solar Smart Clock - Multi-View with Touch Navigation"""

import os
import time
import math
import datetime
from zoneinfo import ZoneInfo
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
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")


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
LIGHT_GRAY = (180, 180, 180)
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
        self.aqi_data = None
        self.aqi_last_update = 0
        self.fonts = self._load_fonts()
        self.view_manager = ViewManager()
        self.touch_handler = TouchHandler(self.view_manager)
        self.fb_handle = open(self.fb_device, "wb")

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
            fonts["tiny"] = ImageFont.truetype(font_path, 16)
            fonts["micro"] = ImageFont.truetype(font_path, 14)
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
        """Get golden hour times - approximately 30 min before/after sunrise and sunset"""
        try:
            sun_times = self.get_sun_times()
            if not sun_times:
                return None, None
            
            sunrise = sun_times.get("sunrise")
            sunset = sun_times.get("sunset")
            
            morning = None
            evening = None
            
            if sunrise:
                # Morning golden hour: 30 min before to 30 min after sunrise
                morning = (
                    sunrise - datetime.timedelta(minutes=30),
                    sunrise + datetime.timedelta(minutes=30)
                )
            
            if sunset:
                # Evening golden hour: 30 min before to 30 min after sunset
                evening = (
                    sunset - datetime.timedelta(minutes=30),
                    sunset + datetime.timedelta(minutes=30)
                )
            
            return morning, evening
        except:
            return None, None

    def get_weather(self):
        """Get current weather from OpenWeatherMap"""
        now = time.time()
        if self.weather_data and (now - self.weather_last_update) < 900:
            return self.weather_data
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={LOCATION.latitude}&lon={LOCATION.longitude}&appid={OPENWEATHER_API_KEY}&units=imperial"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Format similar to wttr.in output for compatibility
                temp = data['main']['temp']
                desc = data['weather'][0]['main']
                humidity = data['main']['humidity']
                self.weather_data = f"{desc} {temp:.0f}°F {humidity}%"
                self.weather_last_update = now
        except Exception as e:
            print(f"Weather fetch error: {e}", flush=True)
            if not self.weather_data:
                self.weather_data = "--"
        return self.weather_data

    def get_weather_forecast(self):
        """Get weather forecast from OpenWeatherMap"""
        now = time.time()
        if self.weather_json and (now - self.weather_last_update) < 900:
            return self.weather_json
        try:
            # Current weather
            current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={LOCATION.latitude}&lon={LOCATION.longitude}&appid={OPENWEATHER_API_KEY}&units=imperial"
            current_r = requests.get(current_url, timeout=10)
            
            # 5-day forecast
            forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={LOCATION.latitude}&lon={LOCATION.longitude}&appid={OPENWEATHER_API_KEY}&units=imperial"
            forecast_r = requests.get(forecast_url, timeout=10)
            
            if current_r.status_code == 200 and forecast_r.status_code == 200:
                current_data = current_r.json()
                forecast_data = forecast_r.json()
                
                # Convert to wttr.in-like format for compatibility with existing view code
                self.weather_json = self._convert_openweather_format(current_data, forecast_data)
                self.weather_last_update = now
        except Exception as e:
            print(f"Forecast fetch error: {e}", flush=True)
        return self.weather_json

    def _convert_openweather_format(self, current, forecast):
        """Convert OpenWeatherMap response to wttr.in-like format"""
        result = {
            'current_condition': [{
                'temp_F': str(int(current['main']['temp'])),
                'FeelsLikeF': str(int(current['main']['feels_like'])),
                'humidity': str(current['main']['humidity']),
                'weatherDesc': [{'value': current['weather'][0]['description'].title()}],
                'windspeedMiles': str(int(current['wind']['speed'])),
                'winddir16Point': self._degrees_to_compass(current['wind'].get('deg', 0))
            }],
            'weather': []
        }
        
        # Group forecast by day
        daily = {}
        for item in forecast['list']:
            date = item['dt_txt'].split(' ')[0]
            if date not in daily:
                daily[date] = {'temps': [], 'rain': [], 'hourly': []}
            daily[date]['temps'].append(item['main']['temp'])
            # Check for rain probability
            rain_chance = int(item.get('pop', 0) * 100)
            daily[date]['rain'].append(rain_chance)
            daily[date]['hourly'].append({
                'chanceofrain': str(rain_chance),
                'weatherDesc': [{'value': item['weather'][0]['description'].title()}]
            })
        
        # Build daily forecast
        for date, data in list(daily.items())[:4]:
            day_data = {
                'date': date,
                'maxtempF': str(int(max(data['temps']))),
                'mintempF': str(int(min(data['temps']))),
                'hourly': data['hourly']
            }
            result['weather'].append(day_data)
        
        return result

    def _degrees_to_compass(self, degrees):
        """Convert wind degrees to 16-point compass direction"""
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                      'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        idx = int((degrees + 11.25) / 22.5) % 16
        return directions[idx]


    def get_solstice_equinox_dates(self, year):
        """Get solstice and equinox dates for a year using ephem"""
        if not EPHEM_AVAILABLE:
            return {
                'spring_equinox': datetime.date(year, 3, 20),
                'summer_solstice': datetime.date(year, 6, 21),
                'fall_equinox': datetime.date(year, 9, 22),
                'winter_solstice': datetime.date(year, 12, 21),
            }

        try:
            dates = {}
            spring = ephem.next_vernal_equinox(f"{year}/1/1")
            dates['spring_equinox'] = ephem.Date(spring).datetime().date()
            summer = ephem.next_summer_solstice(f"{year}/1/1")
            dates['summer_solstice'] = ephem.Date(summer).datetime().date()
            fall = ephem.next_autumnal_equinox(f"{year}/1/1")
            dates['fall_equinox'] = ephem.Date(fall).datetime().date()
            winter = ephem.next_winter_solstice(f"{year}/1/1")
            dates['winter_solstice'] = ephem.Date(winter).datetime().date()
            return dates
        except Exception as e:
            print(f"Solstice/equinox calculation error: {e}", flush=True)
            return {
                'spring_equinox': datetime.date(year, 3, 20),
                'summer_solstice': datetime.date(year, 6, 21),
                'fall_equinox': datetime.date(year, 9, 22),
                'winter_solstice': datetime.date(year, 12, 21),
            }

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

    def get_moon_rise_set(self):
        """Get moonrise and moonset times for today using ephem"""
        if not EPHEM_AVAILABLE:
            return None, None

        try:
            obs = ephem.Observer()
            obs.lat = str(LOCATION.latitude)
            obs.lon = str(LOCATION.longitude)
            obs.date = datetime.datetime.now(datetime.timezone.utc)

            moon = ephem.Moon()

            # Get next moonrise and moonset
            try:
                next_rise = obs.next_rising(moon)
                rise_time = ephem.Date(next_rise).datetime()
                # Convert to local timezone
                tz = ZoneInfo(LOCATION.timezone)
                rise_time = rise_time.replace(tzinfo=datetime.timezone.utc).astimezone(tz)
            except:
                rise_time = None

            try:
                next_set = obs.next_setting(moon)
                set_time = ephem.Date(next_set).datetime()
                tz = ZoneInfo(LOCATION.timezone)
                set_time = set_time.replace(tzinfo=datetime.timezone.utc).astimezone(tz)
            except:
                set_time = None

            return rise_time, set_time
        except Exception as e:
            print(f"Moon rise/set error: {e}")
            return None, None

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
        """Enhanced sun arc with better visuals"""
        # Horizon line
        draw.line([(cx - radius - 5, cy), (cx + radius + 5, cy)], fill=GRAY, width=2)

        # Draw arc path with subtle shading
        for i in range(0, 180, 5):
            a1, a2 = math.radians(i), math.radians(i + 5)
            x1 = cx - int(radius * math.cos(a1))
            y1 = cy - int(radius * math.sin(a1))
            x2 = cx - int(radius * math.cos(a2))
            y2 = cy - int(radius * math.sin(a2))
            arc_color = (60, 60, 80) if i < 90 else (40, 40, 60)
            draw.line([(x1, y1), (x2, y2)], fill=arc_color, width=2)

        # Sun position marker
        if elev is not None:
            if elev >= 0:
                # Sun is up - position on arc
                angle = math.radians(180 - elev * 2)
                sx = cx - int(radius * 0.85 * math.cos(angle))
                sy = cy - int(radius * 0.85 * math.sin(angle))

                # Glow effect
                draw.ellipse([(sx-12, sy-12), (sx+12, sy+12)], fill=(80, 60, 0))
                draw.ellipse([(sx-10, sy-10), (sx+10, sy+10)], fill=(120, 80, 0))
                # Sun body
                draw.ellipse([(sx-8, sy-8), (sx+8, sy+8)], fill=YELLOW, outline=WHITE, width=2)

                # Small rays
                for ray_angle in range(0, 360, 45):
                    rad = math.radians(ray_angle)
                    rx1 = sx + int(9 * math.cos(rad))
                    ry1 = sy - int(9 * math.sin(rad))
                    rx2 = sx + int(13 * math.cos(rad))
                    ry2 = sy - int(13 * math.sin(rad))
                    draw.line([(rx1, ry1), (rx2, ry2)], fill=YELLOW, width=2)
            else:
                # Sun is below horizon - show position below line
                below_amount = min(abs(elev) / 18, 1.0)
                sx = cx
                sy = cy + int(15 * below_amount)
                draw.ellipse([(sx-5, sy-5), (sx+5, sy+5)], fill=PURPLE, outline=GRAY)

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
        """Main clock view - improved layout"""
        now = datetime.datetime.now()
        hour = now.hour

        # Time-based header color
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
        date_str = now.strftime("%A, %B %-d, %Y")
        bbox = draw.textbbox((0, 0), date_str, font=self.fonts["small"])
        tw = bbox[2] - bbox[0]
        draw.text((WIDTH//2 - tw//2, 58), date_str, fill=WHITE, font=self.fonts["small"])

        # === LEFT SIDE ===
        sun_times = self.get_sun_times()

        # Sun times in a styled box
        draw.rounded_rectangle([(8, 88), (225, 148)], radius=6, fill=(25, 25, 35))
        if sun_times:
            sunrise = sun_times["sunrise"].strftime("%-I:%M %p")
            sunset = sun_times["sunset"].strftime("%-I:%M %p")
            # Sunrise with sun icon
            draw.ellipse([(15, 96), (27, 108)], fill=YELLOW)
            draw.text((32, 94), sunrise, fill=YELLOW, font=self.fonts["med"])
            # Sunset with setting sun icon
            draw.arc([(15, 124), (27, 136)], 180, 360, fill=ORANGE, width=2)
            draw.line([(15, 130), (27, 130)], fill=ORANGE, width=2)
            draw.text((32, 120), sunset, fill=ORANGE, font=self.fonts["med"])

            # Day length on right side of box
            day_len = sun_times["sunset"] - sun_times["sunrise"]
            hours = int(day_len.total_seconds() // 3600)
            mins = int((day_len.total_seconds() % 3600) // 60)
            draw.text((145, 94), f"{hours}h {mins}m", fill=WHITE, font=self.fonts["small"])
            draw.text((145, 114), "daylight", fill=GRAY, font=self.fonts["tiny"])

        # Weather box with better formatting
        weather = self.get_weather()
        if weather:
            draw.rounded_rectangle([(8, 155), (225, 195)], radius=6, fill=(25, 25, 35))
            # Parse weather string: "Clouds 45°F 62%"
            parts = weather.split()
            if len(parts) >= 2:
                condition = parts[0]
                temp = parts[1] if len(parts) > 1 else ""
                humidity = parts[2] if len(parts) > 2 else ""

                # Weather condition with color coding
                if "rain" in condition.lower() or "drizzle" in condition.lower():
                    cond_color = LIGHT_BLUE
                elif "cloud" in condition.lower():
                    cond_color = LIGHT_GRAY
                elif "clear" in condition.lower() or "sun" in condition.lower():
                    cond_color = YELLOW
                elif "snow" in condition.lower():
                    cond_color = WHITE
                else:
                    cond_color = LIGHT_GRAY

                draw.text((16, 161), condition[:10], fill=cond_color, font=self.fonts["med"])
                draw.text((130, 161), temp, fill=WHITE, font=self.fonts["med"])
                if humidity:
                    draw.text((185, 166), humidity, fill=LIGHT_BLUE, font=self.fonts["small"])

        # Day progress bar
        draw.rounded_rectangle([(8, 205), (225, 228)], radius=5, fill=(25, 25, 35))
        mins_of_day = now.hour * 60 + now.minute
        prog = mins_of_day / 1440
        bar_width = int(209 * prog)
        if bar_width > 3:
            draw.rounded_rectangle([(10, 207), (10 + bar_width, 226)], radius=4, fill=BLUE)
        draw.text((85, 232), f"{prog*100:.0f}% of day", fill=LIGHT_GRAY, font=self.fonts["tiny"])

        # === RIGHT SIDE ===
        elev, azim = self.get_solar_position()

        # Solar position box
        draw.rounded_rectangle([(235, 88), (WIDTH - 8, 175)], radius=6, fill=(25, 25, 35))

        # Title
        draw.text((245, 92), "Sun Position", fill=LIGHT_GRAY, font=self.fonts["small"])

        if elev is not None:
            # Current elevation
            elev_color = YELLOW if elev > 0 else PURPLE
            draw.text((245, 112), f"{elev:.1f}°", fill=elev_color, font=self.fonts["med"])
            status = "above" if elev > 0 else "below"
            draw.text((310, 117), status, fill=GRAY, font=self.fonts["tiny"])

            # Azimuth with compass direction
            if azim < 45 or azim >= 315:
                direction = "N"
            elif azim < 135:
                direction = "E"
            elif azim < 225:
                direction = "S"
            else:
                direction = "W"
            draw.text((245, 140), f"{azim:.0f}° {direction}", fill=LIGHT_GRAY, font=self.fonts["small"])

        # Improved sun arc
        self.draw_sun_arc(draw, elev, 360, 220, 50)

        # Next event countdown (bottom right)
        next_event, time_delta, event_color = self.get_next_solar_event()
        if next_event and time_delta:
            total_secs = int(time_delta.total_seconds())
            hours = total_secs // 3600
            mins = (total_secs % 3600) // 60
            evt_name = next_event.replace(" (tomorrow)", "")
            draw.text((235, 240), f"{evt_name} in {hours}h {mins}m",
                     fill=event_color or ORANGE, font=self.fonts["tiny"])

        # Navigation bar
        self.draw_nav_bar(draw)

        return img

    def get_next_solar_event(self):
        """Get the next solar event and time remaining"""
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
        """Sun path view - full day elevation chart"""
        tz = ZoneInfo(LOCATION.timezone)
        now = datetime.datetime.now(tz)
        today = now.date()

        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        sun_times = self.get_sun_times()
        elev, azim = self.get_solar_position()

        # Layout constants
        header_h = 42
        nav_y = HEIGHT - NAV_BAR_HEIGHT  # 280
        bottom_h = 58
        bottom_y = nav_y - bottom_h - 4  # 218
        chart_box_top = header_h + 4  # 36
        chart_box_bottom = bottom_y - 4  # 214

        # Header
        draw.rectangle([(0, 0), (WIDTH, header_h)], fill=ORANGE)
        title = "Sun Path"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["med"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 4), title, fill=WHITE, font=self.fonts["med"])

        # Chart area with margins for labels
        margin_left = 32
        margin_right = 10
        margin_top = 8
        margin_bottom = 16  # Space for hour labels
        
        chart_left = margin_left
        chart_right = WIDTH - margin_right
        chart_top = chart_box_top + margin_top
        chart_bottom = chart_box_bottom - margin_bottom
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top

        # Chart background box
        draw.rounded_rectangle([(8, chart_box_top), (WIDTH - 8, chart_box_bottom)], 
                               radius=6, fill=(15, 15, 25))

        # Calculate dynamic elevation range based on today's sun path
        max_elev_today = 0
        min_elev_today = 0
        for mins in range(0, 24 * 60, 30):
            check_time = datetime.datetime.combine(today, datetime.time(0, 0), tzinfo=tz)
            check_time += datetime.timedelta(minutes=mins)
            try:
                check_utc = check_time.astimezone(datetime.timezone.utc)
                e = elevation(LOCATION.observer, check_utc)
                if e > max_elev_today:
                    max_elev_today = e
                if e < min_elev_today:
                    min_elev_today = e
            except:
                pass
        
        # Round max up to nearest 10, min down to nearest 10
        max_elev = max(((int(max_elev_today) // 10) + 1) * 10, 40)
        min_elev = min(((int(min_elev_today) // 10) - 1) * 10, -20)
        elev_range = max_elev - min_elev

        def elev_to_y(e):
            normalized = (e - min_elev) / elev_range
            return int(chart_bottom - normalized * chart_height)

        def time_to_x(dt):
            if isinstance(dt, datetime.datetime):
                hours = dt.hour + dt.minute / 60 + dt.second / 3600
            else:
                hours = dt
            return int(chart_left + (hours / 24) * chart_width)

        # Twilight zone backgrounds (clipped to chart area)
        civil_y = min(max(elev_to_y(0), chart_top), chart_bottom)
        nautical_y = min(max(elev_to_y(-6), chart_top), chart_bottom)
        astro_y = min(max(elev_to_y(-12), chart_top), chart_bottom)

        # Draw zones
        draw.rectangle([(chart_left, astro_y), (chart_right, chart_bottom)], fill=(20, 20, 40))
        draw.rectangle([(chart_left, nautical_y), (chart_right, astro_y)], fill=(30, 30, 55))
        draw.rectangle([(chart_left, civil_y), (chart_right, nautical_y)], fill=(40, 45, 70))
        draw.rectangle([(chart_left, chart_top), (chart_right, civil_y)], fill=(50, 60, 90))

        # Horizon line
        draw.line([(chart_left, civil_y), (chart_right, civil_y)], fill=WHITE, width=2)

        # Hour grid and labels
        for hour in [0, 6, 12, 18, 24]:
            x = time_to_x(hour)
            draw.line([(x, chart_top), (x, chart_bottom)], fill=(60, 60, 80), width=1)
            if hour < 24:
                lbl = f"{hour:02d}"
                draw.text((x - 6, chart_bottom + 2), lbl, fill=GRAY, font=self.fonts["micro"])
            else:
                draw.text((x - 6, chart_bottom + 2), "24", fill=GRAY, font=self.fonts["micro"])

        # Sun elevation curve
        path_points = []
        for mins in range(0, 24 * 60 + 1, 10):
            check_time = datetime.datetime.combine(today, datetime.time(0, 0), tzinfo=tz)
            check_time += datetime.timedelta(minutes=mins)
            try:
                check_utc = check_time.astimezone(datetime.timezone.utc)
                e = elevation(LOCATION.observer, check_utc)
                x = time_to_x(mins / 60)
                y = elev_to_y(e)
                # Clamp to chart bounds
                y = max(chart_top, min(chart_bottom, y))
                path_points.append((x, y, e))
            except:
                pass

        # Draw curve with color by elevation - thick with outline for visibility
        if len(path_points) > 1:
            # First pass: dark outline
            for i in range(len(path_points) - 1):
                x1, y1, e1 = path_points[i]
                x2, y2, e2 = path_points[i + 1]
                draw.line([(x1, y1), (x2, y2)], fill=(0, 0, 0), width=10)
            
            # Second pass: white glow
            for i in range(len(path_points) - 1):
                x1, y1, e1 = path_points[i]
                x2, y2, e2 = path_points[i + 1]
                draw.line([(x1, y1), (x2, y2)], fill=(40, 40, 40), width=7)
            
            # Third pass: colored line on top
            for i in range(len(path_points) - 1):
                x1, y1, e1 = path_points[i]
                x2, y2, e2 = path_points[i + 1]
                if e1 >= 0:
                    color = YELLOW
                elif e1 >= -6:
                    color = ORANGE
                elif e1 >= -12:
                    color = PURPLE
                else:
                    color = (120, 120, 180)
                draw.line([(x1, y1), (x2, y2)], fill=color, width=4)

        # Event markers on curve
        if sun_times:
            for key, color in [("dawn", LIGHT_BLUE), ("sunrise", YELLOW), 
                               ("noon", WHITE), ("sunset", ORANGE), ("dusk", PURPLE)]:
                evt_time = sun_times.get(key)
                if evt_time:
                    try:
                        evt_utc = evt_time.astimezone(datetime.timezone.utc)
                        e = elevation(LOCATION.observer, evt_utc)
                        x = time_to_x(evt_time)
                        y = max(chart_top, min(chart_bottom, elev_to_y(e)))
                        draw.ellipse([(x-3, y-3), (x+3, y+3)], fill=color)
                    except:
                        pass

        # Current position - prominent sun marker
        if elev is not None:
            x = time_to_x(now)
            y = max(chart_top, min(chart_bottom, elev_to_y(elev)))
            
            # Vertical time line
            draw.line([(x, chart_top), (x, chart_bottom)], fill=(100, 100, 120), width=1)
            
            # Sun glow (outer rings)
            draw.ellipse([(x-12, y-12), (x+12, y+12)], fill=(80, 60, 0))
            draw.ellipse([(x-10, y-10), (x+10, y+10)], fill=(120, 80, 0))
            
            # Sun body
            draw.ellipse([(x-8, y-8), (x+8, y+8)], fill=ORANGE, outline=WHITE, width=2)
            draw.ellipse([(x-5, y-5), (x+5, y+5)], fill=YELLOW)
            
            # Sun rays (small lines radiating out)
            ray_len = 6
            for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
                rad = angle * 3.14159 / 180
                rx1 = x + int(10 * math.cos(rad))
                ry1 = y - int(10 * math.sin(rad))
                rx2 = x + int((10 + ray_len) * math.cos(rad))
                ry2 = y - int((10 + ray_len) * math.sin(rad))
                draw.line([(rx1, ry1), (rx2, ry2)], fill=YELLOW, width=2)

        # Y-axis labels (dynamic)
        draw.text((10, chart_top - 2), f"{max_elev}°", fill=GRAY, font=self.fonts["micro"])
        mid_elev = max_elev // 2
        mid_y = elev_to_y(mid_elev)
        draw.text((10, mid_y - 5), f"{mid_elev}°", fill=GRAY, font=self.fonts["micro"])
        draw.text((14, civil_y - 5), "0°", fill=WHITE, font=self.fonts["micro"])
        draw.text((10, chart_bottom - 10), f"{min_elev}°", fill=GRAY, font=self.fonts["micro"])

        # BOTTOM SECTION
        box_gap = 6
        right_box_w = 95
        left_box_w = WIDTH - 16 - box_gap - right_box_w

        # Left box - countdown
        draw.rounded_rectangle([(8, bottom_y), (8 + left_box_w, nav_y - 4)], 
                               radius=6, fill=(25, 25, 35))
        
        next_event, time_delta, event_color = self.get_next_solar_event()
        
        if next_event and time_delta:
            evt_name = next_event.replace(" (tomorrow)", "").capitalize()
            total_secs = int(time_delta.total_seconds())
            hours = total_secs // 3600
            mins = (total_secs % 3600) // 60
            
            # Line 1: Dawn in Xh Ym
            x = 16
            draw.text((x, bottom_y + 5), evt_name, fill=event_color or ORANGE, font=self.fonts["med"])
            bbox = draw.textbbox((x, bottom_y + 5), evt_name, font=self.fonts["med"])
            x = bbox[2] + 6
            
            draw.text((x, bottom_y + 9), "in", fill=GRAY, font=self.fonts["small"])
            x += 24
            
            draw.text((x, bottom_y + 5), str(hours), fill=YELLOW, font=self.fonts["med"])
            bbox = draw.textbbox((x, bottom_y + 5), str(hours), font=self.fonts["med"])
            x = bbox[2] + 2
            draw.text((x, bottom_y + 9), "h", fill=GRAY, font=self.fonts["small"])
            x += 18
            
            draw.text((x, bottom_y + 5), str(mins), fill=YELLOW, font=self.fonts["med"])
            bbox = draw.textbbox((x, bottom_y + 5), str(mins), font=self.fonts["med"])
            x = bbox[2] + 2
            draw.text((x, bottom_y + 9), "m", fill=GRAY, font=self.fonts["small"])
            
            # Line 2: at X:XX am
            for key in ["dawn", "sunrise", "noon", "sunset", "dusk"]:
                if key in next_event.lower():
                    evt_time = sun_times.get(key) if sun_times else None
                    if evt_time:
                        time_str = evt_time.strftime("%-I:%M %p").lower()
                        draw.text((16, bottom_y + 34), "at", fill=GRAY, font=self.fonts["small"])
                        draw.text((40, bottom_y + 34), time_str, fill=WHITE, font=self.fonts["small"])
                    break
        else:
            draw.text((18, bottom_y + 20), "--", fill=GRAY, font=self.fonts["med"])

        # Right box - position (compact)
        right_x = WIDTH - 8 - right_box_w
        draw.rounded_rectangle([(right_x, bottom_y), (WIDTH - 8, nav_y - 4)], 
                               radius=6, fill=(25, 25, 35))
        
        if elev is not None:
            elev_color = YELLOW if elev > 0 else (ORANGE if elev > -6 else PURPLE)
            draw.text((right_x + 8, bottom_y + 8), f"El {elev:.0f}°", fill=elev_color, font=self.fonts["med"])
            draw.text((right_x + 8, bottom_y + 34), f"Az {azim:.0f}°", fill=LIGHT_GRAY, font=self.fonts["small"])
        else:
            draw.text((right_x + 8, bottom_y + 20), "--", fill=GRAY, font=self.fonts["med"])

        self.draw_nav_bar(draw)
        return img


    def draw_weather_icon(self, draw, x, y, size, condition):
        """Draw a simple weather icon based on condition"""
        condition = condition.lower()

        if "clear" in condition or "sunny" in condition:
            # Sun icon
            r = size // 2
            draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=YELLOW)
            # Rays
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                rx1 = x + int((r + 3) * math.cos(rad))
                ry1 = y - int((r + 3) * math.sin(rad))
                rx2 = x + int((r + 7) * math.cos(rad))
                ry2 = y - int((r + 7) * math.sin(rad))
                draw.line([(rx1, ry1), (rx2, ry2)], fill=YELLOW, width=2)
        elif "cloud" in condition:
            # Cloud icon
            draw.ellipse([(x - 10, y - 5), (x, y + 5)], fill=LIGHT_GRAY)
            draw.ellipse([(x - 5, y - 10), (x + 8, y + 3)], fill=LIGHT_GRAY)
            draw.ellipse([(x, y - 5), (x + 12, y + 7)], fill=LIGHT_GRAY)
        elif "rain" in condition or "drizzle" in condition:
            # Cloud with rain drops
            draw.ellipse([(x - 8, y - 8), (x, y)], fill=GRAY)
            draw.ellipse([(x - 4, y - 12), (x + 6, y - 2)], fill=GRAY)
            draw.ellipse([(x, y - 8), (x + 10, y + 2)], fill=GRAY)
            # Rain drops
            for dx, dy in [(-5, 8), (0, 6), (5, 10)]:
                draw.line([(x + dx, y + dy), (x + dx - 2, y + dy + 6)], fill=LIGHT_BLUE, width=2)
        elif "snow" in condition:
            # Snowflakes
            for dx, dy in [(-6, 0), (6, 0), (0, -6)]:
                draw.text((x + dx - 4, y + dy - 6), "*", fill=WHITE, font=self.fonts["small"])
        elif "thunder" in condition or "storm" in condition:
            # Cloud with lightning
            draw.ellipse([(x - 8, y - 10), (x + 2, y - 2)], fill=GRAY)
            draw.ellipse([(x - 4, y - 14), (x + 8, y - 4)], fill=GRAY)
            # Lightning bolt
            draw.polygon([(x, y), (x - 3, y + 8), (x + 2, y + 5), (x - 1, y + 14)], fill=YELLOW)
        else:
            # Default: partly cloudy
            draw.ellipse([(x - 8, y - 5), (x + 2, y + 5)], fill=LIGHT_GRAY)
            draw.ellipse([(x - 4, y - 10), (x + 8, y)], fill=LIGHT_GRAY)

    def create_weather_frame(self):
        """Weather forecast view - with visual indicators"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=BLUE)
        title = "Weather"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 6), title, fill=WHITE, font=self.fonts["large"])

        forecast = self.get_weather_forecast()

        # LEFT SIDE - Current conditions (single box)
        if forecast and 'current_condition' in forecast:
            cc = forecast['current_condition'][0]
            temp = cc.get('temp_F', '--')
            feels = cc.get('FeelsLikeF', '--')
            humidity = cc.get('humidity', '--')
            desc = cc.get('weatherDesc', [{}])[0].get('value', '')[:18]
            wind_speed = cc.get('windspeedMiles', '0')
            wind_dir = cc.get('winddir16Point', 'N')

            # Main conditions box
            draw.rounded_rectangle([(8, 48), (190, 235)], radius=8, fill=(25, 25, 35), outline=(70, 70, 90), width=1)

            # Weather icon in top right of box
            self.draw_weather_icon(draw, 160, 75, 12, desc)

            # Large temperature
            draw.text((18, 52), f"{temp}°F", fill=WHITE, font=self.fonts["huge"])

            # Feels like and humidity on same row
            draw.text((18, 108), f"Feels {feels}°", fill=LIGHT_GRAY, font=self.fonts["small"])
            draw.text((115, 108), f"{humidity}%", fill=LIGHT_BLUE, font=self.fonts["small"])

            # Weather description with condition-based color
            desc_lower = desc.lower()
            if "rain" in desc_lower or "drizzle" in desc_lower:
                desc_color = LIGHT_BLUE
            elif "clear" in desc_lower or "sunny" in desc_lower:
                desc_color = YELLOW
            elif "cloud" in desc_lower:
                desc_color = LIGHT_GRAY
            elif "snow" in desc_lower:
                desc_color = WHITE
            else:
                desc_color = LIGHT_BLUE
            draw.text((18, 135), desc, fill=desc_color, font=self.fonts["small"])

            # Separator line
            draw.line([(18, 162), (180, 162)], fill=DARK_GRAY, width=1)

            # Wind with visual direction indicator
            draw.text((18, 172), "Wind", fill=LIGHT_GRAY, font=self.fonts["small"])
            draw.text((18, 195), f"{wind_speed} mph {wind_dir}", fill=WHITE, font=self.fonts["med"])

        draw.text((15, 245), f"{LOCATION.name}", fill=LIGHT_GRAY, font=self.fonts["tiny"])

        # RIGHT SIDE - Forecast table
        if forecast and 'weather' in forecast:
            x = 200
            col_day = x + 8
            col_high = x + 80
            col_low = x + 140
            col_rain = x + 200
            y = 52

            draw.text((col_day, y), "Day", fill=LIGHT_GRAY, font=self.fonts["small"])
            draw.text((col_high, y), "Hi", fill=LIGHT_GRAY, font=self.fonts["small"])
            draw.text((col_low, y), "Lo", fill=LIGHT_GRAY, font=self.fonts["small"])
            draw.text((col_rain, y), "Rain", fill=LIGHT_GRAY, font=self.fonts["small"])

            y += 22
            draw.line([(x, y), (WIDTH - 10, y)], fill=GRAY, width=1)
            y += 6

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

                row_y = y + i * 58
                draw.rounded_rectangle([(x, row_y), (WIDTH - 10, row_y + 52)], radius=6, fill=(20, 20, 30))
                draw.text((col_day, row_y + 15), day_name, fill=WHITE, font=self.fonts["med"])
                draw.text((col_high, row_y + 15), f"{max_temp}°", fill=(255, 180, 50), font=self.fonts["med"])
                draw.text((col_low, row_y + 15), f"{min_temp}°", fill=(100, 180, 255), font=self.fonts["med"])

                # Rain chance with visual bar
                rain_val = int(rain_chance) if rain_chance.isdigit() else 0
                if rain_val > 50:
                    rain_color = (100, 200, 255)
                    # Draw rain drop icon for high chance
                    drop_x = col_rain + 50
                    draw.polygon([(drop_x, row_y + 12), (drop_x - 4, row_y + 20), (drop_x + 4, row_y + 20)], fill=LIGHT_BLUE)
                    draw.ellipse([(drop_x - 4, row_y + 17), (drop_x + 4, row_y + 25)], fill=LIGHT_BLUE)
                elif rain_val > 20:
                    rain_color = (150, 180, 200)
                else:
                    rain_color = GRAY
                draw.text((col_rain, row_y + 15), f"{rain_chance}%", fill=rain_color, font=self.fonts["med"])

        self.draw_nav_bar(draw)
        return img


    def create_moon_frame(self):
        """Moon phase view - with rise/set times"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=PURPLE)
        title = "Moon Phase"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 6), title, fill=WHITE, font=self.fonts["large"])

        moon = self.get_moon_phase()

        if moon:
            # LEFT SIDE - Moon visualization in a box
            draw.rounded_rectangle([(10, 50), (175, 270)], radius=8, fill=(15, 15, 25))
            moon_cy = 120
            self.draw_moon(draw, 92, moon_cy, 55, moon['phase'])

            # Phase name centered below moon
            phase_name = moon['phase_name']
            bbox = draw.textbbox((0, 0), phase_name, font=self.fonts["small"])
            name_w = bbox[2] - bbox[0]
            draw.text((92 - name_w//2, 185), phase_name, fill=MOON_YELLOW, font=self.fonts["small"])

            # Moonrise/Moonset in bottom of left box
            moon_rise, moon_set = self.get_moon_rise_set()
            if moon_rise or moon_set:
                draw.line([(20, 210), (165, 210)], fill=DARK_GRAY, width=1)
                if moon_rise:
                    rise_str = moon_rise.strftime("%-I:%M %p")
                    draw.text((20, 218), "Rise", fill=GRAY, font=self.fonts["tiny"])
                    draw.text((20, 234), rise_str, fill=LIGHT_GRAY, font=self.fonts["small"])
                if moon_set:
                    set_str = moon_set.strftime("%-I:%M %p")
                    draw.text((95, 218), "Set", fill=GRAY, font=self.fonts["tiny"])
                    draw.text((95, 234), set_str, fill=LIGHT_GRAY, font=self.fonts["small"])

            # RIGHT SIDE - Moon info box
            draw.rounded_rectangle([(185, 50), (WIDTH - 10, 270)], radius=8, fill=(25, 25, 35), outline=(60, 60, 80))

            # Illumination - large and prominent
            draw.text((195, 58), "Illumination", fill=LIGHT_GRAY, font=self.fonts["small"])
            draw.text((195, 78), f"{moon['illumination']:.0f}%", fill=WHITE, font=self.fonts["large"])

            # Illumination bar
            bar_width = int((moon['illumination'] / 100) * 90)
            draw.rounded_rectangle([(195, 112), (285, 122)], radius=3, fill=DARK_GRAY)
            if bar_width > 2:
                draw.rounded_rectangle([(195, 112), (195 + bar_width, 122)], radius=3, fill=MOON_YELLOW)

            # Separator
            draw.line([(195, 132), (WIDTH - 20, 132)], fill=DARK_GRAY, width=1)

            # Next new moon
            next_new = moon['next_new']
            new_str = next_new.strftime("%b %-d")
            days_to_new = (next_new.date() - datetime.date.today()).days
            draw.text((195, 140), "New Moon", fill=LIGHT_GRAY, font=self.fonts["small"])
            draw.text((195, 160), new_str, fill=WHITE, font=self.fonts["med"])
            draw.text((290, 163), f"{days_to_new}d", fill=LIGHT_BLUE, font=self.fonts["small"])

            # Next full moon
            next_full = moon['next_full']
            full_str = next_full.strftime("%b %-d")
            days_to_full = (next_full.date() - datetime.date.today()).days
            draw.text((195, 190), "Full Moon", fill=LIGHT_GRAY, font=self.fonts["small"])
            draw.text((195, 210), full_str, fill=WHITE, font=self.fonts["med"])
            draw.text((290, 213), f"{days_to_full}d", fill=MOON_YELLOW, font=self.fonts["small"])

            # Current phase progress indicator at bottom
            draw.text((195, 240), "Lunar cycle", fill=GRAY, font=self.fonts["tiny"])
            cycle_bar_width = int(moon['phase'] * 90)
            draw.rounded_rectangle([(195, 255), (285, 263)], radius=3, fill=DARK_GRAY)
            if cycle_bar_width > 2:
                draw.rounded_rectangle([(195, 255), (195 + cycle_bar_width, 263)], radius=3, fill=PURPLE)

        else:
            draw.text((WIDTH//2 - 100, 120), "Moon data unavailable",
                     fill=GRAY, font=self.fonts["med"])
            draw.text((WIDTH//2 - 80, 150), "(install ephem library)",
                     fill=DARK_GRAY, font=self.fonts["small"])

        # Navigation bar
        self.draw_nav_bar(draw)

        return img


    def create_solar_frame(self):
        """Detailed solar information view - cleaner layout"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=ORANGE)
        title = "Solar Details"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 6), title, fill=WHITE, font=self.fonts["large"])

        sun_times = self.get_sun_times()
        elev, azim = self.get_solar_position()

        # LEFT COLUMN - Sun times box
        draw.rounded_rectangle([(8, 50), (235, 175)], radius=8, fill=(25, 25, 35), outline=(60, 60, 80))
        
        y = 58
        if sun_times:
            dawn = sun_times.get("dawn")
            sunrise = sun_times.get("sunrise")
            noon = sun_times.get("noon")
            sunset = sun_times.get("sunset")
            dusk = sun_times.get("dusk")

            # Dawn
            if dawn:
                draw.text((18, y), "Dawn", fill=LIGHT_GRAY, font=self.fonts["small"])
                draw.text((90, y), dawn.strftime("%-I:%M %p"), fill=LIGHT_BLUE, font=self.fonts["small"])
                y += 22

            # Sunrise
            if sunrise:
                draw.text((18, y), "Sunrise", fill=LIGHT_GRAY, font=self.fonts["small"])
                draw.text((90, y), sunrise.strftime("%-I:%M %p"), fill=YELLOW, font=self.fonts["small"])
                y += 22

            # Noon
            if noon:
                draw.text((18, y), "Noon", fill=LIGHT_GRAY, font=self.fonts["small"])
                draw.text((90, y), noon.strftime("%-I:%M %p"), fill=WHITE, font=self.fonts["small"])
                y += 22

            # Sunset
            if sunset:
                draw.text((18, y), "Sunset", fill=LIGHT_GRAY, font=self.fonts["small"])
                draw.text((90, y), sunset.strftime("%-I:%M %p"), fill=ORANGE, font=self.fonts["small"])
                y += 22

            # Dusk
            if dusk:
                draw.text((18, y), "Dusk", fill=LIGHT_GRAY, font=self.fonts["small"])
                draw.text((90, y), dusk.strftime("%-I:%M %p"), fill=PURPLE, font=self.fonts["small"])

        # RIGHT COLUMN - Position and day length
        draw.rounded_rectangle([(245, 50), (WIDTH - 8, 175)], radius=8, fill=(25, 25, 35), outline=(60, 60, 80))
        
        # Day length
        if sun_times:
            sunrise = sun_times.get("sunrise")
            sunset = sun_times.get("sunset")
            if sunrise and sunset:
                day_len = sunset - sunrise
                hours = int(day_len.total_seconds() // 3600)
                mins = int((day_len.total_seconds() % 3600) // 60)
                draw.text((255, 58), "Day Length", fill=LIGHT_GRAY, font=self.fonts["small"])
                draw.text((255, 80), f"{hours}h {mins}m", fill=WHITE, font=self.fonts["med"])

        # Current position
        draw.text((255, 115), "Sun Position", fill=LIGHT_GRAY, font=self.fonts["small"])
        if elev is not None:
            status = "up" if elev > 0 else "down"
            elev_color = YELLOW if elev > 0 else PURPLE
            draw.text((255, 137), f"{elev:.1f}° {status}", fill=elev_color, font=self.fonts["med"])
            
            # Direction
            if azim < 90:
                direction = "NE"
            elif azim < 180:
                direction = "SE"
            elif azim < 270:
                direction = "SW"
            else:
                direction = "NW"
            draw.text((370, 140), direction, fill=LIGHT_GRAY, font=self.fonts["small"])

        # BOTTOM - Golden hours (compact)
        morning_gh, evening_gh = self.get_golden_hour()
        
        # Morning golden hour
        draw.rounded_rectangle([(8, 183), (235, 230)], radius=6, fill=(40, 35, 20))
        draw.text((18, 190), "Morning Golden Hour", fill=YELLOW, font=self.fonts["small"])
        if morning_gh:
            start_t = morning_gh[0].strftime("%-I:%M")
            end_t = morning_gh[1].strftime("%-I:%M %p")
            draw.text((18, 208), f"{start_t} - {end_t}", fill=ORANGE, font=self.fonts["small"])
        else:
            draw.text((18, 208), "--", fill=GRAY, font=self.fonts["small"])
        
        # Evening golden hour
        draw.rounded_rectangle([(245, 183), (WIDTH - 8, 230)], radius=6, fill=(40, 30, 25))
        draw.text((255, 190), "Evening Golden Hour", fill=YELLOW, font=self.fonts["small"])
        if evening_gh:
            start_t = evening_gh[0].strftime("%-I:%M")
            end_t = evening_gh[1].strftime("%-I:%M %p")
            draw.text((255, 208), f"{start_t} - {end_t}", fill=ORANGE, font=self.fonts["small"])
        else:
            draw.text((255, 208), "--", fill=GRAY, font=self.fonts["small"])

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
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=aqi_color if aqi > 0 else DARK_GRAY)
        header_text = "Air Quality"
        bbox = draw.textbbox((0, 0), header_text, font=self.fonts["large"])
        tw = bbox[2] - bbox[0]
        text_color = BLACK if aqi in [1, 2] else WHITE
        draw.text((WIDTH//2 - tw//2, 8), header_text, fill=text_color, font=self.fonts["large"])

        # Left side: Large AQI display
        aqi_y = 55
        draw.text((25, aqi_y), "AQI Level", fill=LIGHT_GRAY, font=self.fonts["small"])
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
        draw.text((25, info_y), f"{LOCATION.name}", fill=LIGHT_GRAY, font=self.fonts["small"])
        if aqi == 0:
            draw.text((200, info_y), "API key activating...", fill=ORANGE, font=self.fonts["small"])
        elif hasattr(self, 'aqi_last_update') and self.aqi_last_update > 0:
            update_time = datetime.datetime.fromtimestamp(self.aqi_last_update).strftime("%-I:%M %p")
            draw.text((200, info_y), f"Updated {update_time}", fill=LIGHT_GRAY, font=self.fonts["small"])

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
        """Day length chart for full year - with solstice/equinox info"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 42)], fill=YELLOW)
        title = "Day Length"
        bbox = draw.textbbox((0, 0), title, font=self.fonts["large"])
        draw.text((WIDTH//2 - (bbox[2] - bbox[0])//2, 6), title, fill=BLACK, font=self.fonts["large"])

        # Chart area
        chart_left = 42
        chart_right = WIDTH - 12
        chart_top = 48
        chart_bottom = 175
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top

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
            draw.text((100, 100), "No data available", fill=GRAY, font=self.fonts["med"])
            self.draw_nav_bar(draw)
            return img

        min_dl = min(dl for _, dl, _ in day_lengths)
        max_dl = max(dl for _, dl, _ in day_lengths)
        dl_range = max_dl - min_dl

        min_entry = min(day_lengths, key=lambda x: x[1])
        max_entry = max(day_lengths, key=lambda x: x[1])

        # Chart background
        draw.rounded_rectangle([(chart_left - 2, chart_top - 2),
                                (chart_right + 2, chart_bottom + 2)],
                               radius=4, fill=(15, 15, 25))

        # Y axis labels
        for hours in range(int(min_dl), int(max_dl) + 2, 2):
            if min_dl <= hours <= max_dl:
                y = chart_bottom - int((hours - min_dl) / dl_range * chart_height)
                draw.text((5, y - 6), f"{hours}h", fill=GRAY, font=self.fonts["micro"])
                draw.line([(chart_left, y), (chart_right, y)], fill=(40, 40, 50), width=1)

        # X axis months
        months = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
        for i, m in enumerate(months):
            x = chart_left + int((i + 0.5) * chart_width / 12)
            draw.text((x - 3, chart_bottom + 3), m, fill=GRAY, font=self.fonts["micro"])

        # Solstice/equinox dates
        sol_eq = self.get_solstice_equinox_dates(year)
        events = [
            ('spring_equinox', 'Vernal', LIGHT_BLUE),
            ('summer_solstice', 'Summer', YELLOW),
            ('fall_equinox', 'Autumn', ORANGE),
            ('winter_solstice', 'Winter', BLUE),
        ]

        # Draw vertical lines for solstice/equinox
        for key, label, color in events:
            evt_date = sol_eq[key]
            day_num = evt_date.timetuple().tm_yday
            x = chart_left + int((day_num - 1) / 365 * chart_width)
            draw.line([(x, chart_top), (x, chart_bottom)], fill=color, width=2)

        # Draw day length curve
        points = []
        for day_of_year, dl, date in day_lengths:
            x = chart_left + int((day_of_year - 1) / 365 * chart_width)
            y = chart_bottom - int((dl - min_dl) / dl_range * chart_height)
            points.append((x, y))

        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=ORANGE, width=2)

        # Mark today
        today_day = today.timetuple().tm_yday
        today_dl = self.calculate_day_length(today)
        today_x = chart_left + int((today_day - 1) / 365 * chart_width)
        today_y = chart_bottom - int((today_dl - min_dl) / dl_range * chart_height)
        draw.ellipse([(today_x - 7, today_y - 7), (today_x + 7, today_y + 7)], fill=(80, 60, 0))
        draw.ellipse([(today_x - 5, today_y - 5), (today_x + 5, today_y + 5)], fill=WHITE, outline=YELLOW)

        # === INFO PANEL ===
        info_top = 196
        box_h = 68

        # Today box - compact
        box1_w = 118
        draw.rounded_rectangle([(8, info_top), (8 + box1_w, info_top + box_h)], radius=6, fill=(25, 25, 35), outline=(60, 60, 80))
        hours = int(today_dl)
        mins = int((today_dl - hours) * 60)
        draw.text((15, info_top + 5), "Today", fill=LIGHT_GRAY, font=self.fonts["small"])
        draw.text((15, info_top + 22), f"{hours}h {mins}m", fill=WHITE, font=self.fonts["med"])

        # Trend
        yesterday = today - datetime.timedelta(days=1)
        yesterday_dl = self.calculate_day_length(yesterday)
        diff_mins = (today_dl - yesterday_dl) * 60
        if diff_mins > 0.1:
            trend_text = f"+{diff_mins:.1f}m/day"
            trend_color = YELLOW
        elif diff_mins < -0.1:
            trend_text = f"{diff_mins:.1f}m/day"
            trend_color = LIGHT_BLUE
        else:
            trend_text = "~0m/day"
            trend_color = GRAY
        draw.text((15, info_top + 48), trend_text, fill=trend_color, font=self.fonts["small"])

        # Min/Max box - wider with side-by-side layout
        box2_x = 8 + box1_w + 6
        box2_w = 180
        draw.rounded_rectangle([(box2_x, info_top), (box2_x + box2_w, info_top + box_h)], radius=6, fill=(25, 25, 35), outline=(60, 60, 80))
        
        # Shortest column
        min_hours = int(min_dl)
        min_mins = int((min_dl - min_hours) * 60)
        col1_x = box2_x + 8
        draw.text((col1_x, info_top + 5), "Shortest", fill=BLUE, font=self.fonts["tiny"])
        draw.text((col1_x, info_top + 20), f"{min_hours}h {min_mins}m", fill=WHITE, font=self.fonts["small"])
        draw.text((col1_x, info_top + 40), min_entry[2].strftime("%b %d"), fill=GRAY, font=self.fonts["tiny"])
        
        # Longest column
        max_hours = int(max_dl)
        max_mins = int((max_dl - max_hours) * 60)
        col2_x = box2_x + 95
        draw.text((col2_x, info_top + 5), "Longest", fill=YELLOW, font=self.fonts["tiny"])
        draw.text((col2_x, info_top + 20), f"{max_hours}h {max_mins}m", fill=WHITE, font=self.fonts["small"])
        draw.text((col2_x, info_top + 40), max_entry[2].strftime("%b %d"), fill=GRAY, font=self.fonts["tiny"])

        # Next event box
        box3_x = box2_x + box2_w + 6
        draw.rounded_rectangle([(box3_x, info_top), (WIDTH - 8, info_top + box_h)], radius=6, fill=(25, 25, 35), outline=(60, 60, 80))
        next_event = None
        next_event_name = None
        next_event_color = None
        for key, label, color in events:
            evt_date = sol_eq[key]
            if evt_date > today:
                next_event = evt_date
                next_event_name = label
                next_event_color = color
                break
        if next_event is None:
            next_year_events = self.get_solstice_equinox_dates(year + 1)
            next_event = next_year_events['spring_equinox']
            next_event_name = "Vernal"
            next_event_color = LIGHT_BLUE

        days_until = (next_event - today).days
        draw.text((box3_x + 8, info_top + 5), "Next", fill=LIGHT_GRAY, font=self.fonts["tiny"])
        draw.text((box3_x + 8, info_top + 20), next_event_name, fill=next_event_color, font=self.fonts["small"])
        draw.text((box3_x + 8, info_top + 40), next_event.strftime("%b %d"), fill=WHITE, font=self.fonts["tiny"])
        # Days count on right side
        days_str = str(days_until)
        bbox = draw.textbbox((0, 0), days_str, font=self.fonts["med"])
        days_w = bbox[2] - bbox[0]
        draw.text((WIDTH - 16 - days_w, info_top + 14), days_str, fill=next_event_color, font=self.fonts["med"])
        draw.text((WIDTH - 16 - days_w, info_top + 42), "days", fill=GRAY, font=self.fonts["tiny"])

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
        """Analemma chart - improved with explanations and seasonal colors"""
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

        # Explanation subtitle
        draw.text((WIDTH//2 - 115, 46), "Sun's noon position through the year", fill=GRAY, font=self.fonts["tiny"])

        # Chart area - shifted to allow info panel
        chart_cx = 160
        chart_cy = 155

        eot_scale = 6
        decl_scale = 3.5

        # Draw chart background
        draw.rounded_rectangle([(20, 58), (300, 235)], radius=8, fill=(15, 15, 25))

        # Draw axes with better labels
        # Vertical axis (declination = sun height)
        draw.line([(chart_cx, 65), (chart_cx, 230)], fill=(50, 50, 60), width=1)
        # Horizontal axis (equation of time = sun fast/slow)
        draw.line([(30, chart_cy), (290, chart_cy)], fill=(50, 50, 60), width=1)

        # Simplified axis labels
        draw.text((chart_cx + 5, 63), "Summer", fill=YELLOW, font=self.fonts["micro"])
        draw.text((chart_cx + 5, 220), "Winter", fill=LIGHT_BLUE, font=self.fonts["micro"])
        draw.text((25, chart_cy - 12), "Sun", fill=GRAY, font=self.fonts["micro"])
        draw.text((25, chart_cy + 2), "early", fill=GRAY, font=self.fonts["micro"])
        draw.text((260, chart_cy - 12), "Sun", fill=GRAY, font=self.fonts["micro"])
        draw.text((260, chart_cy + 2), "late", fill=GRAY, font=self.fonts["micro"])

        # Calculate analemma points as continuous curve
        today = datetime.date.today()
        year = today.year
        sol_eq = self.get_solstice_equinox_dates(year)
        
        # Season colors
        season_colors = {
            'spring': (100, 200, 100),  # Green
            'summer': YELLOW,
            'fall': ORANGE,
            'winter': LIGHT_BLUE
        }
        
        def get_season(date):
            if date < sol_eq['spring_equinox']:
                return 'winter'
            elif date < sol_eq['summer_solstice']:
                return 'spring'
            elif date < sol_eq['fall_equinox']:
                return 'summer'
            elif date < sol_eq['winter_solstice']:
                return 'fall'
            else:
                return 'winter'
        
        # Collect all points in order
        all_points = []
        for day_of_year in range(1, 366, 2):
            try:
                date = datetime.date(year, 1, 1) + datetime.timedelta(days=day_of_year - 1)
                eot, decl = self.calculate_analemma_point(date)
                if eot is not None:
                    x = chart_cx + int(eot * eot_scale)
                    y = chart_cy - int(decl * decl_scale)
                    season = get_season(date)
                    all_points.append((x, y, date, season))
            except:
                pass
        
        # Draw as continuous curve with season colors
        if len(all_points) > 1:
            for i in range(len(all_points) - 1):
                x1, y1, date1, season1 = all_points[i]
                x2, y2, date2, season2 = all_points[i + 1]
                color = season_colors[season1]
                draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
            # Close the loop - connect last point to first
            x1, y1, _, season1 = all_points[-1]
            x2, y2, _, _ = all_points[0]
            draw.line([(x1, y1), (x2, y2)], fill=season_colors[season1], width=3)

        # Mark today's position
        today_eot, today_decl = self.calculate_analemma_point(today)
        if today_eot is not None:
            today_x = chart_cx + int(today_eot * eot_scale)
            today_y = chart_cy - int(today_decl * decl_scale)
            draw.ellipse([(today_x - 8, today_y - 8), (today_x + 8, today_y + 8)], fill=(80, 60, 0))
            draw.ellipse([(today_x - 6, today_y - 6), (today_x + 6, today_y + 6)], fill=WHITE)

        # Right panel - today's info
        info_x = 310
        draw.rounded_rectangle([(info_x, 58), (WIDTH - 8, 235)], radius=8, fill=(25, 25, 35), outline=(60, 60, 80))

        draw.text((info_x + 10, 65), "Today", fill=WHITE, font=self.fonts["small"])

        if today_eot is not None:
            # Sun early or late
            if today_eot > 0.5:
                timing = "late"
                timing_color = ORANGE
            elif today_eot < -0.5:
                timing = "early"
                timing_color = YELLOW
            else:
                timing = "on time"
                timing_color = WHITE

            draw.text((info_x + 10, 88), "Sun is", fill=GRAY, font=self.fonts["tiny"])
            draw.text((info_x + 10, 103), f"{abs(today_eot):.1f} min", fill=timing_color, font=self.fonts["med"])
            draw.text((info_x + 10, 128), timing, fill=timing_color, font=self.fonts["small"])

            # Declination meaning
            draw.line([(info_x + 10, 150), (WIDTH - 18, 150)], fill=DARK_GRAY, width=1)

            if today_decl > 0:
                height = "high"
                height_color = YELLOW
            else:
                height = "low"
                height_color = LIGHT_BLUE

            draw.text((info_x + 10, 158), "Sun path", fill=GRAY, font=self.fonts["tiny"])
            draw.text((info_x + 10, 173), height, fill=height_color, font=self.fonts["med"])
            draw.text((info_x + 10, 198), f"{abs(today_decl):.1f}° {['S','N'][today_decl > 0]}", fill=GRAY, font=self.fonts["small"])

        # Season legend at bottom
        legend_y = 218
        legend_items = [('Sp', (100, 200, 100)), ('Su', YELLOW), ('Fa', ORANGE), ('Wi', LIGHT_BLUE)]
        lx = info_x + 10
        for label, color in legend_items:
            draw.ellipse([(lx, legend_y), (lx + 8, legend_y + 8)], fill=color)
            draw.text((lx + 12, legend_y - 2), label, fill=GRAY, font=self.fonts["micro"])
            lx += 35

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
        self.fb_handle.seek(0)
        self.fb_handle.write(fb)

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
