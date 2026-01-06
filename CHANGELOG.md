# Changelog

All notable changes to Solar Smart Clock will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-01-06

### Breaking Changes
- **Configuration**: Settings now loaded from `config.json` instead of hardcoded values
  - Copy `config.example.json` to `config.json` and edit for your location
- **API Key**: OpenWeatherMap API key now loaded from environment file
  - Create `/etc/solar-clock/secrets` with `OPENWEATHER_API_KEY=your_key`
- **Entry Point**: Run with `python -m solar_clock` instead of `python clock.py`

### Added
- **Modular Architecture**: Codebase split into organized modules
  - `solar_clock/config.py` - Configuration loading and validation
  - `solar_clock/display.py` - Framebuffer display handling
  - `solar_clock/http_server.py` - HTTP screenshot server
  - `solar_clock/touch_handler.py` - Touch input processing
  - `solar_clock/data/` - Data providers (weather, solar, lunar)
  - `solar_clock/views/` - Individual view implementations
- **Configuration Validation**: Config file validated on load with clear error messages
- **HTTP Server Security**:
  - Default bind to localhost (127.0.0.1) instead of all interfaces
  - Rate limiting (10 requests/second default)
  - Optional HTTP Basic Auth via environment variables
- **Proper Logging**: Replaced print() with Python logging framework
- **Unit Tests**: Comprehensive test suite with pytest
- **Type Hints**: Full type annotations throughout codebase
- **Requirements Files**: `requirements.txt` and `requirements-dev.txt`

### Changed
- **Error Handling**: All bare `except:` replaced with specific exception types
- **Systemd Service**: Updated to use `EnvironmentFile` for secrets
- **Security Hardening**: Service file includes `NoNewPrivileges`, `ProtectSystem`

### Removed
- **Hardcoded Location**: Must be configured in `config.json`
- **Inline API Key**: No longer stored in code or service file

### Security
- API key no longer committed to repository
- HTTP server secure by default (localhost only)
- Service runs with reduced privileges

## [1.0.0] - Previous Release

Initial release with single-file architecture.

### Features
- 9 interactive views (Clock, Weather, Air Quality, Sun Path, Day Length, Solar Details, Moon Phase, Analemma, Analog Clock)
- Touch navigation (swipe and button tap)
- HTTP screenshot server
- OpenWeatherMap integration
- Astral and ephem calculations
