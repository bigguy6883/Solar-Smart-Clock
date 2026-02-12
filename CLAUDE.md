# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Deployment

**The clock service runs on `clock.local`, NOT on `homelab`.**

- `clock.local` - Raspberry Pi with TFT display (runs the solar-clock service)
- `homelab` - Development machine (code editing, git operations, tests only)

Do not attempt to start/restart the solar-clock service on homelab - it has no display hardware.

## Project Overview

Solar Smart Clock - A modular Python application that renders 9 interactive views to a Waveshare 3.5" TFT LCD touchscreen (480x320) on Raspberry Pi. Writes directly to framebuffer `/dev/fb1` using RGB565 format.

## Commands

```bash
# Run the application
python3 -m solar_clock

# Restart service after code changes
sudo systemctl restart solar-clock

# View live logs
journalctl -u solar-clock -f

# Check service status
sudo systemctl status solar-clock

# Run tests
./venv/bin/pytest tests/ -v

# Run linting
./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503
```

## Remote Screenshot Capture

The clock runs an HTTP server on port 8080 for fast remote screenshots.

### HTTP Endpoints

| Endpoint | Description |
|----------|-------------|
| `/screenshot` | Capture current display as PNG |
| `/health` | Health check (returns "OK") |
| `/next` | Navigate to next view |
| `/prev` | Navigate to previous view |
| `/view` | Get current view name and index |

### From Remote Machine

```bash
# Quick screenshot via HTTP
curl -o /tmp/screen.png http://clock.local:8080/screenshot

# Navigate views
curl http://clock.local:8080/next
curl http://clock.local:8080/view

# Capture all 9 views
for i in 1 2 3 4 5 6 7 8 9; do
    view=$(curl -s http://clock.local:8080/view | cut -d' ' -f1)
    curl -o "/tmp/${i}_${view}.png" http://clock.local:8080/screenshot
    curl -s http://clock.local:8080/next
    sleep 0.3
done
```

## Architecture

### Package Structure

```
solar_clock/
├── __init__.py
├── __main__.py          # Entry point for python -m solar_clock
├── main.py              # SolarClock class, main loop
├── config.py            # Configuration dataclasses and loading
├── display.py           # Framebuffer handling (RGB565)
├── http_server.py       # HTTP API server with rate limiting
├── touch_handler.py     # Touch input (evdev)
├── data/
│   ├── __init__.py
│   ├── weather.py       # WeatherProvider (OpenWeatherMap)
│   ├── solar.py         # SolarProvider (astral)
│   └── lunar.py         # LunarProvider (ephem)
└── views/
    ├── __init__.py      # VIEW_CLASSES list
    ├── base.py          # BaseView, ViewManager, DataProviders, layout constants
    ├── colors.py        # Semantic color definitions (Colors class + flat exports)
    ├── font_manager.py  # FontManager singleton with caching
    ├── layout_helpers.py # Grid/column/centering layout utilities
    ├── renderers.py     # HeaderRenderer, PanelRenderer, NavBarRenderer
    ├── theme.py         # Theme, ThemeManager, DAY_THEME/NIGHT_THEME
    ├── clock.py         # ClockView
    ├── weather.py       # WeatherView
    ├── airquality.py    # AirQualityView
    ├── sunpath.py       # SunPathView
    ├── daylength.py     # DayLengthView
    ├── solar.py         # SolarView
    ├── moon.py          # MoonView
    ├── analemma.py      # AnalemmaView
    └── analogclock.py   # AnalogClockView
```

### Core Classes

| Module | Class | Purpose |
|--------|-------|---------|
| `main.py` | `SolarClock` | Main application - initializes components, runs main loop |
| `config.py` | `Config` | Configuration container with validation |
| `display.py` | `Display` | Framebuffer operations (open, write, RGB565 conversion) |
| `http_server.py` | `ScreenshotHandler` | HTTP request handler for API endpoints |
| `http_server.py` | `RateLimiter` | Token bucket rate limiting |
| `touch_handler.py` | `TouchHandler` | Threaded evdev input for swipes and taps |
| `views/base.py` | `BaseView` | Abstract base for all views |
| `views/base.py` | `ViewManager` | View navigation and rendering |
| `views/base.py` | `DataProviders` | Container for weather/solar/lunar providers |
| `views/theme.py` | `Theme` | Frozen dataclass defining a color theme |
| `views/theme.py` | `ThemeManager` | Singleton managing auto/day/night theme switching |
| `views/font_manager.py` | `FontManager` | Singleton font cache with preloading |
| `views/renderers.py` | `NavBarRenderer` | Bottom nav bar with page indicator dots |

### View System

Views inherit from `BaseView` and implement `render_content()`. The base class handles navigation bar rendering.

| Index | View | Class | File |
|-------|------|-------|------|
| 0 | clock | `ClockView` | `views/clock.py` |
| 1 | weather | `WeatherView` | `views/weather.py` |
| 2 | airquality | `AirQualityView` | `views/airquality.py` |
| 3 | sunpath | `SunPathView` | `views/sunpath.py` |
| 4 | daylength | `DayLengthView` | `views/daylength.py` |
| 5 | solar | `SolarView` | `views/solar.py` |
| 6 | moon | `MoonView` | `views/moon.py` |
| 7 | analemma | `AnalemmaView` | `views/analemma.py` |
| 8 | analogclock | `AnalogClockView` | `views/analogclock.py` |

### Data Flow

1. `main.py:SolarClock.__init__()` - Initializes providers, views, display, HTTP server, touch handler
2. `main.py:SolarClock.run()` - Main loop, renders current view every `update_interval` seconds
3. `views/base.py:ViewManager.render_current()` - Calls current view's `render()` method
4. `views/base.py:BaseView.render()` - Creates image, calls `render_content()`, adds nav bar
5. `display.py:Display.write_frame()` - Converts to RGB565, writes to `/dev/fb1`

### Data Providers

| Provider | Library | Data |
|----------|---------|------|
| `WeatherProvider` | requests | Current weather, 3-day forecast, AQI (OpenWeatherMap) |
| `SolarProvider` | astral | Sunrise, sunset, dawn, dusk, golden hour, sun position |
| `LunarProvider` | ephem | Moon phase, illumination, solstice/equinox dates |

## Configuration

Configuration is loaded from `config.json` (searched in cwd, `~/.config/solar-clock/`, `/etc/solar-clock/`).

### Key Config Sections

```python
@dataclass
class Config:
    location: LocationConfig      # name, region, timezone, lat/lon
    display: DisplayConfig        # width, height, framebuffer, nav_bar_height
    http_server: HttpServerConfig # enabled, port, bind_address, rate_limit
    weather: WeatherConfig        # update_interval_seconds, units
    air_quality: AirQualityConfig # update_interval_seconds
    touch: TouchConfig            # enabled, device, swipe/tap thresholds
    appearance: AppearanceConfig  # default_view, theme_mode (auto/day/night)
```

### Example config.json

```json
{
  "location": {
    "name": "City",
    "region": "State, Country",
    "timezone": "America/New_York",
    "latitude": 40.7128,
    "longitude": -74.0060
  },
  "http_server": {
    "bind_address": "0.0.0.0"
  }
}
```

### Environment Variables

- `OPENWEATHER_API_KEY` - Required for weather/AQI data
- `HTTP_AUTH_USER` / `HTTP_AUTH_PASS` - Optional HTTP Basic Auth

## Key Constants

Colors are defined in `views/colors.py` as a semantic `Colors` class (e.g. `Colors.Solar.SUN`, `Colors.AQI.GOOD`) with flat backward-compatible exports (`BLACK`, `WHITE`, `YELLOW`, etc.). Legacy color constants also remain in `views/base.py` for existing imports.

Layout constants (`Spacing`, `Layout`, `FontSize`) are in `views/base.py`.

## Adding a New View

1. Create `views/newview.py` with class inheriting from `BaseView`
2. Set class attributes: `name`, `title`, `update_interval`
3. Implement `render_content(self, draw, image)` method
4. Add to `VIEW_CLASSES` list in `views/__init__.py`

View count validation is dynamic (`len(VIEW_CLASSES)`), no config changes needed.

## Testing Views

```bash
# Navigate to specific view and capture
curl http://clock.local:8080/next  # repeat as needed
curl http://clock.local:8080/view  # check current view
curl -o test.png http://clock.local:8080/screenshot
```

## Privacy

Before committing, redact: location coordinates in config.json, API keys, IP addresses.
