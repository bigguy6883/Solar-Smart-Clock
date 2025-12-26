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


class ViewManager:
    """Manages navigation between views"""
    VIEWS = ["clock", "weather", "moon", "solar"]

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
    """Handles touch input for swipe detection"""

    def __init__(self, view_manager, device_path="/dev/input/event0"):
        self.view_manager = view_manager
        self.device_path = device_path
        self.running = False
        self.thread = None
        self.touch_start_x = None
        self.touch_start_y = None
        self.swipe_threshold = 400  # Raw units (0-4095 range)

    def start(self):
        if not TOUCH_AVAILABLE:
            print("Touch not available (evdev not installed)")
            return
        try:
            self.device = InputDevice(self.device_path)
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            print(f"Touch handler started on {self.device_path}")
        except Exception as e:
            print(f"Could not start touch handler: {e}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)

    def _run(self):
        current_x = None
        current_y = None
        touching = False

        try:
            for event in self.device.read_loop():
                if not self.running:
                    break

                if event.type == ecodes.EV_ABS:
                    if event.code == ecodes.ABS_X:
                        current_x = event.value
                    elif event.code == ecodes.ABS_Y:
                        current_y = event.value

                elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
                    if event.value == 1:  # Touch down
                        touching = True
                        self.touch_start_x = current_x
                        self.touch_start_y = current_y
                    elif event.value == 0 and touching:  # Touch up
                        touching = False
                        if self.touch_start_x is not None and current_x is not None:
                            self._handle_swipe(self.touch_start_x, current_x)
                        self.touch_start_x = None
                        self.touch_start_y = None
        except Exception as e:
            print(f"Touch handler error: {e}")

    def _handle_swipe(self, start_x, end_x):
        delta = end_x - start_x
        if abs(delta) > self.swipe_threshold:
            if delta > 0:
                # Swipe right (in raw coords) -> previous view
                self.view_manager.prev_view()
                print(f"Swipe right -> {self.view_manager.get_current()}")
            else:
                # Swipe left -> next view
                self.view_manager.next_view()
                print(f"Swipe left -> {self.view_manager.get_current()}")


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
        else:
            d = ImageFont.load_default()
            fonts = {k: d for k in ["huge", "large", "med", "small", "tiny", "micro"]}
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
            for phase in [0, 6, -6, -12, -18]:  # Different twilight angles
                pass
            # Use astral's twilight function
            civil_dawn, civil_dusk = twilight(LOCATION.observer, today, tzinfo=LOCATION.timezone)
            result['civil'] = (civil_dawn, civil_dusk)
            return result
        except Exception as e:
            return None

    def get_golden_hour(self):
        """Get golden hour times"""
        try:
            today = datetime.date.today()
            # Morning golden hour
            try:
                morning = golden_hour(LOCATION.observer, today, direction=1, tzinfo=LOCATION.timezone)
            except:
                morning = None
            # Evening golden hour
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

            # Phase: 0 = new, 0.5 = full
            phase = moon.phase / 100.0  # Convert to 0-1
            illumination = moon.phase  # Percentage illuminated

            # Calculate next new and full moon
            next_new = ephem.next_new_moon(now)
            next_full = ephem.next_full_moon(now)

            # Determine phase name
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

    def draw_page_indicator(self, draw):
        """Draw page indicator dots at bottom"""
        count = self.view_manager.get_count()
        current = self.view_manager.get_index()

        dot_radius = 4
        dot_spacing = 16
        total_width = (count - 1) * dot_spacing
        start_x = WIDTH // 2 - total_width // 2
        y = HEIGHT - 12

        for i in range(count):
            x = start_x + i * dot_spacing
            if i == current:
                draw.ellipse([(x - dot_radius, y - dot_radius),
                             (x + dot_radius, y + dot_radius)], fill=WHITE)
            else:
                draw.ellipse([(x - dot_radius, y - dot_radius),
                             (x + dot_radius, y + dot_radius)], fill=GRAY, outline=GRAY)

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
            angle = math.radians(180 - elev * 2)  # Map 0-90 to 180-0
            sx = cx - int(radius * 0.8 * math.cos(angle))
            sy = cy - int(radius * 0.8 * math.sin(angle))
            draw.ellipse([(sx-10, sy-10), (sx+10, sy+10)], fill=YELLOW, outline=WHITE)

    def draw_moon(self, draw, cx, cy, radius, phase):
        """Draw moon with phase visualization"""
        # Draw full moon circle (dark side)
        draw.ellipse([(cx - radius, cy - radius),
                     (cx + radius, cy + radius)], fill=DARK_GRAY, outline=GRAY)

        # Draw illuminated portion
        if phase is not None:
            # phase 0 = new (dark), 0.5 = full (bright)
            illum = phase * 2 if phase <= 0.5 else (1 - phase) * 2

            # Create illuminated portion
            if phase <= 0.5:
                # Waxing - right side illuminated
                for y_off in range(-radius, radius + 1):
                    x_edge = int(math.sqrt(max(0, radius * radius - y_off * y_off)))
                    x_inner = int(x_edge * (1 - illum * 2))
                    if x_inner < x_edge:
                        draw.line([(cx + x_inner, cy + y_off), (cx + x_edge, cy + y_off)],
                                 fill=MOON_YELLOW)
            else:
                # Waning - left side illuminated
                for y_off in range(-radius, radius + 1):
                    x_edge = int(math.sqrt(max(0, radius * radius - y_off * y_off)))
                    x_inner = int(x_edge * (1 - illum * 2))
                    if x_inner < x_edge:
                        draw.line([(cx - x_edge, cy + y_off), (cx - x_inner, cy + y_off)],
                                 fill=MOON_YELLOW)

    def create_clock_frame(self):
        """Main clock view - original display"""
        now = datetime.datetime.now()
        hour = now.hour

        # Header color by time of day
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
        draw.rectangle([(0, 0), (WIDTH, 85)], fill=hdr)

        # Time (centered)
        time_str = now.strftime("%I:%M:%S %p")
        bbox = draw.textbbox((0, 0), time_str, font=self.fonts["huge"])
        tw = bbox[2] - bbox[0]
        draw.text((WIDTH//2 - tw//2, 8), time_str, fill=WHITE, font=self.fonts["huge"])

        # Date (centered)
        date_str = now.strftime("%A, %B %d, %Y")
        bbox = draw.textbbox((0, 0), date_str, font=self.fonts["small"])
        tw = bbox[2] - bbox[0]
        draw.text((WIDTH//2 - tw//2, 62), date_str, fill=WHITE, font=self.fonts["small"])

        # === LEFT SIDE: Sun times + Weather ===
        sun_times = self.get_sun_times()
        if sun_times:
            sunrise = sun_times["sunrise"].strftime("%I:%M %p")
            sunset = sun_times["sunset"].strftime("%I:%M %p")
            draw.text((15, 95), f"Rise: {sunrise}", fill=YELLOW, font=self.fonts["med"])
            draw.text((15, 122), f"Set:  {sunset}", fill=ORANGE, font=self.fonts["med"])

        # Weather box
        weather = self.get_weather()
        if weather:
            draw.rounded_rectangle([(10, 155), (225, 195)], radius=6, fill=DARK_GRAY)
            w_clean = weather.encode('ascii', 'ignore').decode()[:20]
            draw.text((18, 165), w_clean, fill=WHITE, font=self.fonts["med"])

        # Day progress
        draw.rounded_rectangle([(10, 210), (225, 230)], radius=5, fill=DARK_GRAY)
        mins = now.hour * 60 + now.minute
        prog = mins / 1440
        bw = int(211 * prog)
        if bw > 2:
            draw.rounded_rectangle([(12, 212), (12 + bw, 228)], radius=4, fill=BLUE)
        draw.text((80, 235), f"{prog*100:.0f}% of day", fill=GRAY, font=self.fonts["tiny"])

        # === RIGHT SIDE: Solar position + Arc ===
        elev, azim = self.get_solar_position()

        draw.text((250, 95), "Solar Position", fill=WHITE, font=self.fonts["med"])
        if elev is not None:
            draw.text((250, 125), f"Elevation: {elev:.1f}", fill=WHITE, font=self.fonts["small"])
            draw.text((250, 148), f"Azimuth: {azim:.1f}", fill=WHITE, font=self.fonts["small"])

        # Sun arc (center at 360, 250 with radius 50)
        self.draw_sun_arc(draw, elev, 360, 245, 50)

        # Page indicator
        self.draw_page_indicator(draw)

        return img

    def create_weather_frame(self):
        """Weather forecast view"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 50)], fill=BLUE)
        draw.text((WIDTH//2 - 80, 12), "Weather Forecast", fill=WHITE, font=self.fonts["large"])

        # Current weather
        weather = self.get_weather()
        if weather:
            w_clean = weather.encode('ascii', 'ignore').decode()
            draw.text((20, 60), f"Now: {w_clean}", fill=WHITE, font=self.fonts["med"])

        # Forecast from JSON
        forecast = self.get_weather_forecast()
        if forecast and 'weather' in forecast:
            y = 95
            for i, day in enumerate(forecast['weather'][:4]):  # Next 4 days
                date = day.get('date', '')
                max_temp = day.get('maxtempF', '--')
                min_temp = day.get('mintempF', '--')

                # Get weather description from hourly
                desc = ""
                if 'hourly' in day and len(day['hourly']) > 4:
                    desc = day['hourly'][4].get('weatherDesc', [{}])[0].get('value', '')[:15]

                # Parse date for day name
                try:
                    dt = datetime.datetime.strptime(date, "%Y-%m-%d")
                    day_name = dt.strftime("%a")
                except:
                    day_name = f"Day {i+1}"

                # Draw forecast row
                draw.rounded_rectangle([(10, y), (470, y + 45)], radius=6, fill=DARK_GRAY)
                draw.text((20, y + 5), day_name, fill=LIGHT_BLUE, font=self.fonts["med"])
                draw.text((80, y + 5), f"H:{max_temp}F", fill=ORANGE, font=self.fonts["med"])
                draw.text((170, y + 5), f"L:{min_temp}F", fill=LIGHT_BLUE, font=self.fonts["med"])
                draw.text((260, y + 8), desc, fill=GRAY, font=self.fonts["small"])

                y += 52
        else:
            draw.text((20, 120), "Forecast unavailable", fill=GRAY, font=self.fonts["med"])

        # Page indicator
        self.draw_page_indicator(draw)

        return img

    def create_moon_frame(self):
        """Moon phase view"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 50)], fill=PURPLE)
        draw.text((WIDTH//2 - 60, 12), "Moon Phase", fill=WHITE, font=self.fonts["large"])

        moon = self.get_moon_phase()

        if moon:
            # Draw large moon
            self.draw_moon(draw, 120, 160, 60, moon['phase'])

            # Moon info on right side
            draw.text((220, 80), moon['phase_name'], fill=MOON_YELLOW, font=self.fonts["large"])
            draw.text((220, 120), f"Illumination: {moon['illumination']:.1f}%",
                     fill=WHITE, font=self.fonts["med"])

            # Next new moon
            next_new = moon['next_new']
            new_str = next_new.strftime("%b %d")
            days_to_new = (next_new.date() - datetime.date.today()).days
            draw.text((220, 160), f"New Moon: {new_str}", fill=GRAY, font=self.fonts["small"])
            draw.text((220, 182), f"({days_to_new} days)", fill=DARK_GRAY, font=self.fonts["tiny"])

            # Next full moon
            next_full = moon['next_full']
            full_str = next_full.strftime("%b %d")
            days_to_full = (next_full.date() - datetime.date.today()).days
            draw.text((220, 210), f"Full Moon: {full_str}", fill=GRAY, font=self.fonts["small"])
            draw.text((220, 232), f"({days_to_full} days)", fill=DARK_GRAY, font=self.fonts["tiny"])
        else:
            draw.text((WIDTH//2 - 100, HEIGHT//2), "Moon data unavailable",
                     fill=GRAY, font=self.fonts["med"])
            draw.text((WIDTH//2 - 80, HEIGHT//2 + 30), "(install ephem library)",
                     fill=DARK_GRAY, font=self.fonts["small"])

        # Page indicator
        self.draw_page_indicator(draw)

        return img

    def create_solar_frame(self):
        """Detailed solar information view"""
        img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 0), (WIDTH, 50)], fill=ORANGE)
        draw.text((WIDTH//2 - 70, 12), "Solar Details", fill=WHITE, font=self.fonts["large"])

        sun_times = self.get_sun_times()
        elev, azim = self.get_solar_position()

        y = 60

        if sun_times:
            # Dawn/Dusk
            dawn = sun_times.get("dawn")
            dusk = sun_times.get("dusk")
            if dawn and dusk:
                draw.text((20, y), f"Dawn: {dawn.strftime('%I:%M %p')}",
                         fill=LIGHT_BLUE, font=self.fonts["med"])
                draw.text((250, y), f"Dusk: {dusk.strftime('%I:%M %p')}",
                         fill=PURPLE, font=self.fonts["med"])
                y += 28

            # Sunrise/Sunset
            sunrise = sun_times.get("sunrise")
            sunset = sun_times.get("sunset")
            if sunrise and sunset:
                draw.text((20, y), f"Sunrise: {sunrise.strftime('%I:%M %p')}",
                         fill=YELLOW, font=self.fonts["med"])
                draw.text((250, y), f"Sunset: {sunset.strftime('%I:%M %p')}",
                         fill=ORANGE, font=self.fonts["med"])
                y += 28

            # Solar noon
            noon = sun_times.get("noon")
            if noon:
                draw.text((20, y), f"Solar Noon: {noon.strftime('%I:%M %p')}",
                         fill=WHITE, font=self.fonts["med"])
                y += 28

            # Day length
            if sunrise and sunset:
                day_len = sunset - sunrise
                hours = int(day_len.total_seconds() // 3600)
                mins = int((day_len.total_seconds() % 3600) // 60)
                draw.text((250, y - 28), f"Day Length: {hours}h {mins}m",
                         fill=GRAY, font=self.fonts["med"])

        # Golden hour
        y += 10
        draw.line([(20, y), (460, y)], fill=DARK_GRAY, width=1)
        y += 10

        morning_gh, evening_gh = self.get_golden_hour()
        draw.text((20, y), "Golden Hour", fill=YELLOW, font=self.fonts["med"])
        y += 28

        if morning_gh:
            draw.text((20, y), f"Morning: {morning_gh[0].strftime('%I:%M')} - {morning_gh[1].strftime('%I:%M %p')}",
                     fill=ORANGE, font=self.fonts["small"])
        else:
            draw.text((20, y), "Morning: --", fill=GRAY, font=self.fonts["small"])
        y += 22

        if evening_gh:
            draw.text((20, y), f"Evening: {evening_gh[0].strftime('%I:%M')} - {evening_gh[1].strftime('%I:%M %p')}",
                     fill=ORANGE, font=self.fonts["small"])
        else:
            draw.text((20, y), "Evening: --", fill=GRAY, font=self.fonts["small"])

        # Current position
        y += 35
        draw.line([(20, y), (460, y)], fill=DARK_GRAY, width=1)
        y += 10

        draw.text((20, y), "Current Position", fill=WHITE, font=self.fonts["med"])
        y += 28

        if elev is not None:
            status = "Above horizon" if elev > 0 else "Below horizon"
            draw.text((20, y), f"Elevation: {elev:.1f} ({status})",
                     fill=YELLOW if elev > 0 else GRAY, font=self.fonts["small"])
            draw.text((280, y), f"Azimuth: {azim:.1f}", fill=WHITE, font=self.fonts["small"])

        # Page indicator
        self.draw_page_indicator(draw)

        return img

    def create_frame(self):
        """Create current view frame"""
        view = self.view_manager.get_current()

        if view == "clock":
            return self.create_clock_frame()
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

        # Start touch handler
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
