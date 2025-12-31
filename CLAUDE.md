# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Solar Smart Clock - A single-file Python application that renders 9 interactive views to a Waveshare 3.5" TFT LCD touchscreen (480x320) on Raspberry Pi. Writes directly to framebuffer `/dev/fb1` using RGB565 format.

## Commands

```bash
# Restart service after code changes
sudo systemctl restart solar-clock

# View live logs
journalctl -u solar-clock -f

# Check service status
sudo systemctl status solar-clock
```

## Remote Screenshot Capture

The clock runs an HTTP server on port 8080 for fast remote screenshots (~155ms vs ~3800ms via SSH).

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
# Quick screenshot via HTTP (fastest)
curl -o /tmp/screen.png http://clock.local:8080/screenshot

# Navigate views
curl http://clock.local:8080/next
curl http://clock.local:8080/view

# Use the clockshot utility (tools/clockshot)
./tools/clockshot /tmp/screenshot.png

# Capture all 9 views
for i in 1 2 3 4 5 6 7 8 9; do
    curl -s http://clock.local:8080/next
    sleep 0.3
    view=$(curl -s http://clock.local:8080/view | cut -d' ' -f1)
    curl -o "/tmp/${i}_${view}.png" http://clock.local:8080/screenshot
done
```

### On the Clock Itself

```bash
# Direct framebuffer capture
fbgrab -d /dev/fb1 /tmp/screenshot.png
```

## Architecture

**Single file**: `clock.py` (~2400 lines) contains everything including HTTP screenshot server.

### Core Classes

| Class | Purpose |
|-------|---------|
| `SolarClock` | Main class - renders frames, manages state, writes to framebuffer |
| `ViewManager` | Tracks current view index (0-8), handles prev/next navigation |
| `TouchHandler` | Threaded evdev input handler for swipe gestures and nav button taps |
| `ScreenshotHandler` | HTTP request handler for remote screenshots and view navigation |

### View System

Views are defined in `ViewManager.VIEWS` list. Each has a corresponding `create_*_frame()` method:

| Index | View | Method |
|-------|------|--------|
| 0 | clock | `create_clock_frame()` |
| 1 | weather | `create_weather_frame()` |
| 2 | airquality | `create_airquality_frame()` |
| 3 | sunpath | `create_sunpath_frame()` |
| 4 | daylength | `create_daylength_frame()` |
| 5 | solar | `create_solar_frame()` |
| 6 | moon | `create_moon_frame()` |
| 7 | analemma | `create_analemma_frame()` |
| 8 | analogclock | `create_analogclock_frame()` |

### Data Flow

1. `run()` - Main loop, calls `create_frame()` every 1s
2. `create_frame()` - Dispatches to appropriate `create_*_frame()` based on current view
3. `write_fb()` - Converts PIL Image to RGB565 and writes to `/dev/fb1`
4. `_start_http_server()` - Launches threaded HTTP server on port 8080

### External APIs

All weather/AQI data from OpenWeatherMap (API key in systemd environment):
- `get_weather()` - Current conditions (15 min cache)
- `get_weather_forecast()` - 3-day forecast (15 min cache)
- `get_air_quality()` - AQI and pollutants (30 min cache)

### Local Calculations

- `astral` library: sunrise, sunset, dawn, dusk, golden hour, solar position
- `ephem` library: moon phase, solstice/equinox dates, analemma

## Testing Views

Use HTTP endpoints to navigate and capture views remotely:

```bash
# Switch to specific view and capture
curl http://clock.local:8080/next  # repeat as needed
curl http://clock.local:8080/view  # check current view
curl -o test.png http://clock.local:8080/screenshot
```

## Configuration

Location and timezone are hardcoded in `LOCATION` constant near top of file:
```python
LOCATION = LocationInfo(
    name="City",
    region="State, Country",
    timezone="America/New_York",
    latitude=34.6948,
    longitude=-84.4822
)
```

## Key Constants

- `WIDTH = 480`, `HEIGHT = 320` - Display dimensions
- `NAV_BAR_HEIGHT = 40` - Bottom navigation bar
- Color tuples defined at top (BLACK, WHITE, YELLOW, AQI_* colors, etc.)

## Privacy

Before committing, redact: location coordinates in LOCATION constant, API keys, IP addresses.
