# Solar Smart Clock

A Raspberry Pi-based smart clock displaying time, solar position, sunrise/sunset times, and weather on a Waveshare 3.5" LCD.

## Features

- Current time with AM/PM and date
- Sunrise and sunset times
- Solar elevation and azimuth
- Sun arc visualization
- Weather information (via wttr.in)
- Day progress bar
- Time-based color themes (morning/afternoon/evening/night)

## Hardware Requirements

- Raspberry Pi Zero W (or other Pi model)
- Waveshare 3.5" RPi LCD (Rev 2.0) or compatible SPI display
- Internet connection for weather data

## Installation

1. Enable SPI and configure display in `/boot/firmware/config.txt`:
```
dtparam=spi=on
dtoverlay=waveshare35a:rotate=90
hdmi_force_hotplug=1
hdmi_cvt=480 320 60 6 0 0 0
hdmi_group=2
hdmi_mode=87
```

2. Install dependencies:
```bash
sudo apt-get install python3-pip python3-pil python3-requests
pip3 install --break-system-packages astral ephem
```

3. Copy files:
```bash
mkdir -p ~/solar-clock
cp clock.py ~/solar-clock/
sudo cp solar-clock.service /etc/systemd/system/
```

4. Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable solar-clock
sudo systemctl start solar-clock
```

## Configuration

Edit `clock.py` to change your location:
```python
LOCATION = LocationInfo(
    name="Your City",
    region="State, Country",
    timezone="Your/Timezone",
    latitude=00.0000,
    longitude=-00.0000
)
```

## Commands

```bash
sudo systemctl status solar-clock   # Check status
sudo systemctl restart solar-clock  # Restart
sudo systemctl stop solar-clock     # Stop
journalctl -u solar-clock -f        # View logs
```

## License

MIT
