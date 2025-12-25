#!/usr/bin/env python3
"""Solar Smart Clock - Landscape Mode (Fixed Layout)"""

import os
import time
import math
import datetime
import requests
from PIL import Image, ImageDraw, ImageFont

from astral import LocationInfo
from astral.sun import sun, elevation, azimuth

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

class SolarClock:
    def __init__(self):
        self.fb_device = "/dev/fb1"
        self.weather_data = None
        self.weather_last_update = 0
        self.fonts = self._load_fonts()
        
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
        else:
            d = ImageFont.load_default()
            fonts = {k: d for k in ["huge", "large", "med", "small", "tiny"]}
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
    
    def create_frame(self):
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
        
        # Location footer
        loc = f"{LOCATION.name}, {LOCATION.region}"
        bbox = draw.textbbox((0, 0), loc, font=self.fonts["tiny"])
        tw = bbox[2] - bbox[0]
        draw.text((WIDTH//2 - tw//2, 300), loc, fill=GRAY, font=self.fonts["tiny"])
        
        return img
    
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
        try:
            while True:
                self.write_fb(self.create_frame())
                time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    SolarClock().run()
