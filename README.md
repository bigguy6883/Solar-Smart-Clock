# Solar Smart Clock

A Raspberry Pi-powered smart clock displaying real-time solar data, weather, moon phases, and time on a Waveshare 3.5" TFT LCD touchscreen.

![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-red)
![Python](https://img.shields.io/badge/python-3.x-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

This project was adapted from the original [Solar-Smart-Clock](https://github.com/bigguy6883/Solar-Smart-Clock) Arduino/Pico W project to run on a Raspberry Pi Zero W with a Waveshare 3.5" SPI LCD display. The application renders directly to the Linux framebuffer, providing a lightweight solution without requiring a full desktop environment.

## Features

### Multi-View Interface
Swipe left/right on the touchscreen to navigate between four views:

1. **Clock View** (default)
   - Large, easy-to-read time with AM/PM indicator
   - Full date with day of week
   - Sunrise/sunset times
   - Current weather conditions
   - Day progress bar
   - Solar position (elevation/azimuth) with visual sun arc

2. **Weather Forecast View**
   - Current conditions
   - 4-day forecast with high/low temps
   - Weather descriptions

3. **Moon Phase View**
   - Visual moon phase display
   - Phase name (New, Waxing Crescent, Full, etc.)
   - Illumination percentage
   - Days until next new moon
   - Days until next full moon

4. **Solar Details View**
   - Dawn and dusk times
   - Sunrise and sunset times
   - Solar noon
   - Day length
   - Golden hour times (morning and evening)
   - Current solar elevation and azimuth

### Additional Features
- **Touch Navigation**: Swipe left/right to change views
- **Page Indicator**: Dots at bottom show current view position
- **Dynamic Themes**: Header colors change based on time of day
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

## Software Requirements

- Raspberry Pi OS (Bookworm/Trixie - Debian 12/13)
- Python 3.x
- Required packages:
  - python3-pil - Image processing
  - python3-requests - Weather API calls
  - astral - Sunrise/sunset calculations
  - ephem - Moon phase and astronomical calculations
  - evdev - Touch screen input handling

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

### 3. Install Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-pil python3-requests python3-numpy python3-evdev

pip3 install --break-system-packages astral ephem
```

### 4. Install Solar Clock

```bash
cd ~
git clone https://github.com/bigguy6883/Solar-Smart-Clock.git solar-clock
cd solar-clock
```

### 5. Configure Location

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

### 6. Install Systemd Service

```bash
sudo cp solar-clock.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable solar-clock
sudo systemctl start solar-clock
```

## Usage

### Touch Navigation
- **Swipe Left**: Next view (Clock → Weather → Moon → Solar → Clock)
- **Swipe Right**: Previous view

### Views
The page indicator dots at the bottom show which view is active:
- Dot 1: Clock (main view)
- Dot 2: Weather Forecast
- Dot 3: Moon Phase
- Dot 4: Solar Details

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
```

## File Structure

```
~/solar-clock/
├── clock.py              # Main application
├── solar-clock.service   # Systemd service file
└── README.md             # This file
```

## Technical Details

### Architecture
- **ViewManager**: Handles navigation between the 4 views
- **TouchHandler**: Threaded touch input processor using evdev
- **SolarClock**: Main class rendering frames to framebuffer

### Framebuffer Writing
The application writes directly to `/dev/fb1` using RGB565 format:
```python
rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
```

### External APIs
- Weather: wttr.in (updates every 15 minutes)
- Solar calculations: astral library (local computation)
- Moon phase: ephem library (local computation)

## Future Enhancements

- [ ] Alarm functionality
- [ ] Multiple location support
- [ ] Custom color themes
- [ ] Web configuration interface
- [ ] Additional astronomical data (planets, ISS passes)

## License

MIT License - Feel free to modify and distribute.

## Credits

- Original concept: [Solar-Smart-Clock](https://github.com/bigguy6883/Solar-Smart-Clock)
- Solar calculations: [Astral](https://github.com/sffjunkie/astral)
- Moon calculations: [PyEphem](https://rhodesmill.org/pyephem/)
- Weather data: [wttr.in](https://wttr.in)
- Display drivers: [Waveshare LCD-show](https://github.com/waveshare/LCD-show)
