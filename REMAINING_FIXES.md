# Solar Smart Clock - Remaining Code Fixes

**Created:** 2026-01-06
**Status:** Phases 1-2 Complete, Phases 3-4 Pending
**Repository:** `/home/pi/solar-clock/` on clock.local

---

## Completed Work (Phases 1-2)

| # | Issue | File | Status |
|---|-------|------|--------|
| 1 | Golden hour using astral library | `data/solar.py` | DONE |
| 2 | Timezone-aware datetime handling | `views/clock.py` | DONE (was correct) |
| 3 | Bold font caching | `views/base.py` | DONE |
| 4 | Compass direction consolidation | `views/clock.py` | DONE (reviewed, acceptable) |
| 5 | Equation of time sign | `data/lunar.py` | DONE (reviewed, correct) |
| 6 | Moon panel hierarchy | `views/moon.py` | DONE |
| 7 | Inline imports moved | `views/weather.py`, `views/airquality.py` | DONE |
| 8 | Weather description overflow | `views/weather.py` | DONE |

---

## Phase 3: Medium Priority (Polish)

### Issue 9: Poor Color Contrast on AQI Moderate

**File:** `solar_clock/views/airquality.py`

**Problem:** When AQI is "Moderate" (51-100), the category text uses `AQI_MODERATE` color which is yellow `(255, 255, 0)`. If rendered on dark background it's fine, but the AQI value text color uses this same yellow which can be hard to read.

**Current code at line 31:**
```python
return AQI_MODERATE  # (255, 255, 0) - bright yellow
```

**Fix:** Ensure all AQI text colors have sufficient contrast. Options:
1. Use darker text (`BLACK` or `(40, 40, 40)`) for AQI values on yellow backgrounds
2. Add a dark outline/shadow to yellow text
3. Use a slightly darker yellow `(200, 180, 0)` for text

**Test:** Set a mock AQI of 75 and verify readability.

---

### Issue 10: Hardcoded Layout Y-Positions

**Files:** All view files use magic numbers for vertical positioning.

**Examples found:**
- `clock.py:62` - `self._render_sun_info(draw, 85)`
- `clock.py:65` - `self._render_weather_info(draw, 145)`
- `clock.py:68` - `self._render_day_progress(draw, 230)`
- `weather.py:53` - `draw.text((20, 170), weather.description...`
- `solar.py` - Multiple hardcoded y values

**Fix:** Create layout constants in `base.py`:
```python
# Layout constants
HEADER_HEIGHT = 35
CONTENT_START_Y = 45
ROW_HEIGHT = 50
SECTION_PADDING = 10
```

Then calculate positions:
```python
section1_y = CONTENT_START_Y
section2_y = section1_y + ROW_HEIGHT + SECTION_PADDING
```

**Priority:** Low-medium. Current layout works but is fragile if display size changes.

---

### Issue 11: No-Data States Look Broken

**Files and locations:**
| File | Line | Current Text |
|------|------|--------------|
| `airquality.py` | 97 | `"No data available"` |
| `analemma.py` | 72 | `"Data unavailable"` |
| `clock.py` | 121, 126 | `"Weather: --"` |
| `moon.py` | 39, 45 | `"Lunar data unavailable"` |
| `solar.py` | 51, 56 | `"Solar data unavailable"` |
| `weather.py` | 74, 79 | `"--"` |

**Problems:**
1. Messages positioned inconsistently (some at y=120, some at y+40)
2. All use `GRAY` which has poor contrast on black
3. No visual indication this is an error state

**Fix for each view:**
```python
# Center the message
msg = "Data unavailable"
font = self.get_font(18)
bbox = draw.textbbox((0, 0), msg, font=font)
msg_width = bbox[2] - bbox[0]
x = (self.width - msg_width) // 2
y = self.content_height // 2

# Use LIGHT_GRAY for better contrast
draw.text((x, y), msg, fill=LIGHT_GRAY, font=font)
```

---

### Issue 12: `.lstrip('0')` Time Formatting

**All 11 occurrences:**
```
views/airquality.py:80    - update timestamp
views/clock.py:31         - main time display
views/clock.py:83         - sunrise time
views/clock.py:103        - sunset time
views/moon.py:176         - moonrise time
views/moon.py:179         - moonset time
views/solar.py:73         - sun times
views/solar.py:90         - golden hour morning
views/solar.py:95         - golden hour evening
views/sunpath.py:40       - current time
views/sunpath.py:152      - event time
```

**Problem:** `"09:30 AM".lstrip("0")` produces `"9:30 AM"` (correct), but edge cases exist.

**Better solution:** Use `%-I` format specifier (works on Linux):
```python
# Before
time_str = now.strftime("%I:%M:%S").lstrip("0")

# After
time_str = now.strftime("%-I:%M:%S")
```

**Or create helper in base.py:**
```python
def format_time_12h(self, dt: datetime.datetime, show_seconds: bool = False) -> str:
    """Format time in 12-hour format without leading zero."""
    fmt = "%-I:%M:%S %p" if show_seconds else "%-I:%M %p"
    return dt.strftime(fmt)
```

---

### Issue 13: API Response Parsing Assumes Structure

**File:** `solar_clock/data/weather.py:157-165`

**Current code:**
```python
self._current_weather = CurrentWeather(
    temperature=current_data["main"]["temp"],          # KeyError if missing
    feels_like=current_data["main"]["feels_like"],     # KeyError if missing
    humidity=current_data["main"]["humidity"],         # KeyError if missing
    description=current_data["weather"][0]["description"].title(),  # IndexError if empty
    wind_speed=current_data["wind"]["speed"],          # KeyError if missing
    wind_direction=self._degrees_to_compass(
        current_data["wind"].get("deg", 0)             # This one is safe!
    ),
)
```

**Fix:** Use defensive `.get()` with sensible defaults:
```python
main = current_data.get("main", {})
weather_list = current_data.get("weather", [{}])
wind = current_data.get("wind", {})

self._current_weather = CurrentWeather(
    temperature=main.get("temp", 0),
    feels_like=main.get("feels_like", 0),
    humidity=main.get("humidity", 0),
    description=weather_list[0].get("description", "Unknown").title() if weather_list else "Unknown",
    wind_speed=wind.get("speed", 0),
    wind_direction=self._degrees_to_compass(wind.get("deg", 0)),
)
```

---

### Issue 14: Forecast Dictionary Order Assumed

**File:** `solar_clock/data/weather.py` - `_parse_forecast()` method

**Problem:** Code relies on dict insertion order for chronological display. Python 3.7+ guarantees this, but it's implicit.

**Current behavior:** Forecast items are added to dict as API returns them (usually chronological).

**Safer approach:** Explicitly sort when iterating:
```python
def _render_forecast(self, ...):
    # Sort forecast dates explicitly
    sorted_dates = sorted(self._forecast.keys())
    for date_key in sorted_dates:
        forecast = self._forecast[date_key]
        # render...
```

---

## Phase 4: Low Priority (Maintenance)

### Issue 15: Magic Numbers for Update Intervals

**Current hardcoded values:**
| File | Class | `update_interval` |
|------|-------|-------------------|
| `clock.py` | ClockView | 1 |
| `weather.py` | WeatherView | 60 |
| `airquality.py` | AirQualityView | 60 |
| `moon.py` | MoonView | 3600 |
| `solar.py` | SolarView | 60 |
| `sunpath.py` | SunPathView | 60 |
| `daylength.py` | DayLengthView | 3600 |
| `analemma.py` | AnalemmaView | 3600 |
| `analogclock.py` | AnalogClockView | 1 |

**Fix:** Add to config or create constants:
```python
# In config.py or base.py
UPDATE_REALTIME = 1      # Clock displays
UPDATE_FREQUENT = 60     # Weather, solar position
UPDATE_HOURLY = 3600     # Moon phase, analemma
```

---

### Issue 16: Hardcoded Font Paths

**File:** `solar_clock/views/base.py:109-120`

**Current code:**
```python
self._fonts[size] = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size
)
```

**Problem:** Linux-specific path. Will fail on macOS or if fonts not installed.

**Fix:** Add fallback chain:
```python
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      # Linux
    "/System/Library/Fonts/Helvetica.ttc",                   # macOS
    "/usr/share/fonts/TTF/DejaVuSans.ttf",                  # Arch Linux
]

def get_font(self, size: int) -> ImageFont.FreeTypeFont:
    if size not in self._fonts:
        for path in FONT_PATHS:
            try:
                self._fonts[size] = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
        else:
            self._fonts[size] = ImageFont.load_default()
    return self._fonts[size]
```

---

### Issue 17: View Count Hardcoded in Validation

**File:** `solar_clock/config.py` (exact line TBD)

**Problem:** `default_view` config validated against hardcoded range 0-8.

**Fix:**
```python
from .views import VIEW_CLASSES

def validate_default_view(value: int) -> int:
    if not 0 <= value < len(VIEW_CLASSES):
        raise ValueError(f"default_view must be 0-{len(VIEW_CLASSES)-1}")
    return value
```

---

### Issue 18: Inconsistent Font Sizes

**Problem:** Views use arbitrary font sizes with no system:
- Titles: 24pt (moon), 28pt (weather), varies
- Body: 14pt, 16pt, 18pt mixed
- Values: 20pt, 36pt, 48pt mixed

**Fix:** Define typography scale in `base.py`:
```python
class FontSize:
    TITLE = 24
    SUBTITLE = 20
    BODY = 16
    SMALL = 14
    CAPTION = 12

    VALUE_LARGE = 48
    VALUE_MEDIUM = 36
    VALUE_SMALL = 24
```

---

### Issue 19: Navigation Dots Don't Scale

**File:** `solar_clock/views/base.py:179-215`

**Current:** Fixed 14px spacing between dots regardless of view count.

**Problem:** With 9 views, dots span ~126px. If views added/removed, spacing doesn't adjust.

**Fix:**
```python
def _render_navigation(self, draw, current_index, total_views):
    dot_radius = 4
    dot_spacing = min(14, (self.width - 100) // total_views)  # Dynamic spacing
    total_width = (total_views - 1) * dot_spacing
    start_x = (self.width - total_width) // 2
    # ...
```

---

### Issue 20: Analog Clock Has No Title

**File:** `solar_clock/views/analogclock.py`

**Problem:** Only view without a header bar or title text. Looks inconsistent.

**Options:**
1. Add header bar like other views: `"Analog Clock"` on colored background
2. Add time-based greeting: `"Good Morning"` / `"Good Afternoon"` / `"Good Evening"`
3. Keep minimal but add subtle title at top

**Suggested fix:**
```python
def render_content(self, draw, image):
    # Add minimal header
    font_title = self.get_font(16)
    draw.text((10, 5), "Analog", fill=GRAY, font=font_title)

    # Rest of clock rendering...
```

---

## Quick Reference: File Locations

All paths relative to `/home/pi/solar-clock/solar_clock/`:

| Component | Path |
|-----------|------|
| Base view class | `views/base.py` |
| Clock view | `views/clock.py` |
| Weather view | `views/weather.py` |
| Air quality view | `views/airquality.py` |
| Solar details view | `views/solar.py` |
| Sun path view | `views/sunpath.py` |
| Day length view | `views/daylength.py` |
| Moon view | `views/moon.py` |
| Analemma view | `views/analemma.py` |
| Analog clock view | `views/analogclock.py` |
| Weather provider | `data/weather.py` |
| Solar provider | `data/solar.py` |
| Lunar provider | `data/lunar.py` |
| Config | `config.py` |

---

## Testing Commands

```bash
# SSH to clock
ssh pi@clock.local

# Restart service after changes
sudo systemctl restart solar-clock

# Check for errors
journalctl -u solar-clock -f

# Remote screenshot
curl -o /tmp/test.png http://clock.local:8080/screenshot

# Navigate views
curl http://clock.local:8080/next
curl http://clock.local:8080/prev
curl http://clock.local:8080/view
```

---

## Estimated Remaining Work

| Phase | Issues | Scope |
|-------|--------|-------|
| Phase 3 | 9-14 | 6 issues, ~1 hour |
| Phase 4 | 15-20 | 6 issues, ~30 min |

**Total remaining: 12 issues**
