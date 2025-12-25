# Solar Smart Clock

A Raspberry Pi-powered smart clock displaying real-time solar data, weather, and time on a Waveshare 3.5" TFT LCD display.

![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-red)
![Python](https://img.shields.io/badge/python-3.x-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

This project was adapted from the original [Solar-Smart-Clock](https://github.com/bigguy6883/Solar-Smart-Clock) Arduino/Pico W project to run on a Raspberry Pi Zero W with a Waveshare 3.5" SPI LCD display. The application renders directly to the Linux framebuffer, providing a lightweight solution without requiring a full desktop environment.

## Features

- **Real-time Clock**: Large, easy-to-read time display with AM/PM indicator
- **Date Display**: Full date with day of week
- **Sunrise/Sunset Times**: Calculated daily for your location using the Astral library
- **Solar Position Tracking**:
  - Solar elevation (angle above horizon)
  - Solar azimuth (compass direction)
  - Visual sun arc showing current position
- **Weather Information**: Current conditions fetched from wttr.in (updates every 15 minutes)
- **Day Progress Bar**: Visual indicator of how much of the day has passed
- **Dynamic Themes**: Background colors change based on time of day:
  - Morning (6am-12pm): Light blue
  - Afternoon (12pm-6pm): Blue
  - Evening (6pm-9pm): Orange
  - Night (9pm-6am): Dark blue
- **Auto-start**: Runs automatically on boot via systemd service
- **Landscape Display**: Optimized 480x320 landscape layout

## Hardware Requirements

| Component | Details |
|-----------|---------|
| Raspberry Pi | Pi Zero W, Pi 3, Pi 4, or Pi 5 |
| Display | Waveshare 3.5" RPi LCD (A) Rev 2.0 / Spotpear 3.5" LCD |
| Display Controller | ILI9486 (SPI) |
| Touch Controller | ADS7846 (SPI) |
| Storage | MicroSD card (8GB+) |
| Network | WiFi connection (for weather data) |

### Display Pinout

The Waveshare 3.5" LCD connects directly to the Raspberry Pi 40-pin GPIO header:
- SPI interface for display (SPI0)
- SPI interface for touch (SPI0.1)
- GPIO for control signals

## Software Requirements

- Raspberry Pi OS (Bookworm/Trixie - Debian 12/13)
- Python 3.x
- Required packages:
  - python3-pil - Image processing
  - python3-requests - Weather API calls
  - astral - Sunrise/sunset calculations
  - ephem - Astronomical calculations

## Installation

### 1. Prepare the Display

Clone the Waveshare LCD driver repository:
```bash
cd ~
git clone https://github.com/waveshare/LCD-show.git
```

Copy the display overlay:
```bash
sudo cp ~/LCD-show/waveshare35a-overlay.dtb /boot/firmware/overlays/waveshare35a.dtbo
```

### 2. Configure Boot Settings

Edit `/boot/firmware/config.txt`:
```bash
sudo nano /boot/firmware/config.txt
```

Comment out the KMS driver (if present):
```
#dtoverlay=vc4-kms-v3d
```

Add these lines at the end:
```
# Waveshare 3.5" LCD settings
dtparam=spi=on
dtoverlay=waveshare35a:rotate=90
hdmi_force_hotplug=1
hdmi_cvt=480 320 60 6 0 0 0
hdmi_group=2
hdmi_mode=87
display_rotate=0
```

Reboot to apply changes:
```bash
sudo reboot
```

### 3. Verify Display

After reboot, check that framebuffer devices exist:
```bash
ls -la /dev/fb*
```

You should see:
- `/dev/fb0` - HDMI framebuffer (480x320)
- `/dev/fb1` - LCD framebuffer (480x320)

Test the display:
```bash
cat /dev/urandom > /dev/fb1
# You should see colorful static on the LCD
```

### 4. Install Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-pil python3-requests python3-numpy

pip3 install --break-system-packages astral ephem
```

### 5. Install Solar Clock

```bash
cd ~
git clone https://github.com/bigguy6883/Solar-Smart-Clock.git solar-clock
cd solar-clock
```

### 6. Configure Location

Edit `clock.py` and update the LOCATION settings for your area:
```python
LOCATION = LocationInfo(
    name="Your City",
    region="State, Country",
    timezone="America/New_York",  # Your timezone
    latitude=34.6948,              # Your latitude
    longitude=-84.4822             # Your longitude
)
```

Find your coordinates: [latlong.net](https://www.latlong.net/)

Find your timezone: [Wikipedia Timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

### 7. Install Systemd Service

```bash
sudo cp solar-clock.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable solar-clock
sudo systemctl start solar-clock
```

## File Structure

```
~/solar-clock/
├── clock.py              # Main application
├── solar-clock.service   # Systemd service file
└── README.md             # This file
```

## Configuration Reference

### Display Rotation Options

In `/boot/firmware/config.txt`, change the rotate parameter:
```
dtoverlay=waveshare35a:rotate=0    # Portrait (USB ports on bottom)
dtoverlay=waveshare35a:rotate=90   # Landscape (USB ports on right)
dtoverlay=waveshare35a:rotate=180  # Portrait (USB ports on top)
dtoverlay=waveshare35a:rotate=270  # Landscape (USB ports on left)
```

Remember to update `WIDTH` and `HEIGHT` in `clock.py` accordingly:
- Portrait: `WIDTH=320, HEIGHT=480`
- Landscape: `WIDTH=480, HEIGHT=320`

### Weather Location

The weather is fetched from wttr.in. Update this line in `clock.py`:
```python
r = requests.get("https://wttr.in/YourCity,State?format=%c+%t+%h",
```

### Update Intervals

In `clock.py`:
```python
self.weather_update_interval = 900  # Weather refresh: 900 seconds (15 min)
time.sleep(1)                       # Display refresh: 1 second
```

## Service Management

```bash
# Check status
sudo systemctl status solar-clock

# Start/stop/restart
sudo systemctl start solar-clock
sudo systemctl stop solar-clock
sudo systemctl restart solar-clock

# View live logs
journalctl -u solar-clock -f

# View recent logs
journalctl -u solar-clock --since "1 hour ago"

# Disable auto-start
sudo systemctl disable solar-clock

# Re-enable auto-start
sudo systemctl enable solar-clock
```

## Troubleshooting

### Display shows nothing
1. Check SPI is enabled: `ls /dev/spi*`
2. Verify overlay loaded: `dmesg | grep -i ili9486`
3. Check framebuffer exists: `ls -la /dev/fb1`

### Display shows static/noise
- The display driver is working but no application is writing to it
- Start the clock service: `sudo systemctl start solar-clock`

### Clock service fails to start
```bash
# Check for Python errors
journalctl -u solar-clock -n 50

# Test manually
cd ~/solar-clock
python3 clock.py
```

### Weather shows "unavailable"
- Check internet connectivity: `ping google.com`
- Test weather API: `curl "wttr.in/YourCity?format=%t"`

### Wrong sunrise/sunset times
- Verify latitude/longitude in `clock.py`
- Check timezone setting matches your location

### Display colors look wrong
- The display uses RGB565 format (16-bit color)
- Some color variation is normal for TFT displays

## Technical Details

### Framebuffer Writing

The application writes directly to `/dev/fb1` using RGB565 format:
```python
# RGB888 to RGB565 conversion
rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
```

### Display Driver

The Waveshare 3.5" LCD uses the `fbtft` staging driver:
- Controller: ILI9486
- Interface: SPI @ 16MHz
- Resolution: 320x480 native (rotated to 480x320)
- Color depth: 16-bit (RGB565)

### Touch Screen

The ADS7846 touch controller is available at `/dev/input/event0` but is not currently used by this application. Touch support can be added for future features.

## Session Changes Log

This version was created on December 25, 2025 with the following modifications from the original Pico W project:

1. **Platform Migration**: Converted from Arduino/Pico W to Raspberry Pi + Python
2. **Display Driver**: Configured fbtft driver for Waveshare 3.5" ILI9486 LCD
3. **Framebuffer Rendering**: Implemented direct framebuffer writes using PIL (no X11 required)
4. **Solar Calculations**: Integrated Python `astral` library for accurate sunrise/sunset
5. **Weather Integration**: Added wttr.in API for current weather conditions
6. **Landscape Layout**: Redesigned UI for 480x320 landscape orientation
7. **Systemd Service**: Created auto-start service for headless operation
8. **Removed Sensors**: Light and current sensors from original project not implemented (hardware not available)

## Future Enhancements

Potential additions:
- [ ] Touch screen controls for settings
- [ ] Multiple location support
- [ ] Alarm functionality
- [ ] Moon phase display
- [ ] Weather forecast (multi-day)
- [ ] Custom color themes
- [ ] Web configuration interface

## License

MIT License - Feel free to modify and distribute.

## Credits

- Original concept: [Solar-Smart-Clock](https://github.com/bigguy6883/Solar-Smart-Clock)
- Solar calculations: [Astral](https://github.com/sffjunkie/astral)
- Weather data: [wttr.in](https://wttr.in)
- Display drivers: [Waveshare LCD-show](https://github.com/waveshare/LCD-show)

---

Generated with [Claude Code](https://claude.ai/code)
