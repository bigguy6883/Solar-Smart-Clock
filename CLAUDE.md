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

## Configuration

Configuration is loaded from `config.json` (searched in cwd, `~/.config/solar-clock/`, `/etc/solar-clock/`). Sections and defaults are defined in `config.py` dataclasses.

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

## Privacy

Before committing, redact: location coordinates in config.json, API keys, IP addresses.
