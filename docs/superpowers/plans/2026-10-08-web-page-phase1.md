# Solar Clock Web Page, Phase 1: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve a phone-friendly web page from the running clock at `http://clock.local:8080/` showing five of its nine views (Clock, Weather, Air Quality, Solar Details, Moon Phase), with a home-screen icon, while the physical TFT clock keeps working and looking exactly as it does now.

**Architecture:** The clock's existing single-threaded HTTP server gains read-only routes: `/` and the page's static files from an allowlist, and `/api/now`, which returns JSON built by a new `WebDataService`. That service has its own sun, moon and theme calculators and shares only the weather provider, which gains a non-blocking fetch lock. The browser draws each view itself from that JSON with plain JavaScript modules: no framework, no build step, nothing fetched from the internet.

**Tech Stack:** Python 3.9+ (stdlib `http.server`, astral, ephem, Pillow, all already installed), vanilla ES modules, HTML/CSS/SVG, pytest, Node's built-in test runner (`node --test`, Node 18+; homelab has Node 24).

**Spec:** `docs/superpowers/specs/2026-10-08-web-page-design.md` (approved 2026-10-08). Read it before starting; this plan argues from it.

**Phase 2** (Sun Path, Day Length, Analemma, Analog Clock and `/api/charts`) gets its own plan once phase 1 is deployed and Peter has used it. It reuses this phase's helpers and his feedback on the look.

## How this plan was checked

Every code block below was run before the plan was written (2026-10-08), in a scratch copy of the repo at commit `0d34ba5` with all phase 1 changes applied:

- **Python:** 306 passed, 3 skipped (259 existing + 47 new tests).
- **JavaScript:** 42 passed under Node 24.
- **Linters:** `black --check`, `flake8` (project flags) and `mypy` (project flags) were clean. The new modules were also clean under `mypy --strict` and `ruff 0.16.10 --target-version py39`.
- **TFT pixel parity:** 18 of 18 renders identical (9 views × day and night). The check catches a one-unit colour change.
- **Packaging:** a wheel built from `setup.py` contains all 19 page files.
- **Preview server:** `/`, the static files and `/api/now` answer 200, `/screenshot` answers 503 and `/../config.json` answers 404.

Two things the checks surfaced, so you aren't surprised:

- **Black versions differ.** The venv has black 25.12; the pre-commit hook pins 24.1.1. If the commit hook reformats a file, re-stage it and commit again.
- **Expected console noise.** The `app.js` tests print `Could not reach the clock Error: offline` and `The clock view failed to draw TypeError…`. Those lines come from tests that cause the failures on purpose.

## Global Constraints

- Run everything from the repo root `~/Solar-Smart-Clock` on branch `web-page-phase1`. That branch already holds the spec commits.
- **TFT untouched:** do not modify anything in `solar_clock/views/`, `solar_clock/display.py`, `solar_clock/touch_handler.py`, or the body of `SolarClock.run()` in `solar_clock/main.py`.
- **No existing test is edited.** New tests only; adding imports to an existing test file is fine. Baseline: 262 collected, 259 passed, 3 skipped.
- **Read-only endpoints:** new routes never call `ViewManager` and never call `set_mode` on the clock's `ThemeManager` or `ThemeManager.initialize`.
- **Single-threaded server:** `HTTPServer` stays single-threaded. Do not switch to `ThreadingHTTPServer`; `web_api.py` relies on it.
- **Python 3.9 compatible** (CI runs 3.9–3.12):
  - New modules use `from __future__ import annotations` and may write `X | None` in annotations.
  - Runtime expressions (type aliases, `isinstance`) must not use `X | Y`.
  - No `match` statements.
- **No new dependencies:** no Python packages, no npm packages, no JS framework, no build step, and no request from the page to anything but the clock.
- **Static files:** served only from the allowlist built at startup by walking `solar_clock/web/`. Content types come from exactly this map: `.html`, `.css`, `.js`, `.svg`, `.png`, `.webmanifest` → `application/manifest+json`. Any other extension is not served.
- **Formatting:** page text matches the TFT's strftime patterns, shown in the configured timezone (`config.location.timezone`), not the viewer's. Numbers round like Python's `format()`: exact halves go to even, so 64.5 shows as "64".
- **Messages:** when a data section is `null`, the view shows the same message the TFT shows in that case.
- **Lint gates for every commit:**
  - `./venv/bin/black --check solar_clock tests`
  - `./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503`
  - `./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary`
- **Extra gates for new Python modules** (Peter's global rule): `mypy --strict` and `ruff check --target-version py39` must be clean. Set up ruff once, outside the repo, in your scratchpad: `python3 -m venv <scratchpad>/ruffenv && <scratchpad>/ruffenv/bin/pip install -q ruff==0.16.10`.
  - In existing files you edit, add no new ruff findings, with one exception: FA100 ("add `from __future__ import annotations`"). `http_server.py` and `main.py` already break FA100 12 times, and fixing it means changing those files' imports, so the 2 new FA100 findings from new `Optional[...]` annotations stay.
- **Privacy:** never commit `config.json`, coordinates, API keys or IP addresses.
- **Commits:** end every commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Gated actions:** pushing to GitHub and deploying to clock.local happen only after Peter says so (Task 11).

## Review Focus

These are the five failure modes most likely to bite someone using the page that ordinary per-function tests would miss. Each is pinned by a test in the task that owns the code:

1. **The real `/api/now` drifts from the JavaScript's sample data** (a renamed or missing field): views would show "undefined" on the phone while every JS test passes. Pinned by `tests/test_web_contract.py`, which feeds the real JSON through Node into every view (Task 6).
2. **The clock becomes unreachable mid-session** (Pi reboot, Wi-Fi drop): the page must keep the last data, keep ticking, say "Can't reach clock · last update …", and recover by itself. Pinned by `app.test.mjs` "losing the clock…" (Task 6).
3. **A phone reopens the page from the home screen after hours asleep:** it must fetch fresh data at once, not show hours-old data for up to a minute. Pinned by the same test, which proves `visibilitychange` triggers a poll (Task 6).
4. **The clock switches day/night (or someone hits `/theme/day`) while the page is open:** the page must follow without a reload. Pinned by `app.test.mjs` "a theme change…" (Task 6) and `test_follows_the_clock_theme_mode_without_touching_it` (Task 2).
5. **The TFT tick and a page poll both find the weather cache expired at the same moment:** exactly one API fetch, and the TFT never waits on the page's fetch. Pinned by `TestFetchLock` (Task 1).

## File map

| File | Status | Responsibility |
|---|---|---|
| `solar_clock/data/weather.py` | modify | Non-blocking fetch locks (Task 1) |
| `solar_clock/web_api.py` | create | `WebDataService`: builds `/api/now` with its own sun, moon and theme instances (Task 2) |
| `solar_clock/web_static.py` | create | `StaticSite`: allowlist of page files and content types (Task 3) |
| `solar_clock/http_server.py` | modify | Routes `/`, static files, `/api/now`; static files skip the rate limit (Task 3) |
| `setup.py` | modify | `package_data` for `solar_clock/web/**` (Task 3) |
| `solar_clock/main.py` | modify | Build the page in `SolarClock.__init__`, guarded (Task 4) |
| `tools/web_preview.py` | create | Dev server for the page on homelab (Task 4) |
| `solar_clock/web/package.json` | create | Marks the JS as ES modules for Node; never served (Task 5) |
| `solar_clock/web/js/format.js` | create | TFT-matching text formatting in the clock's timezone (Task 5) |
| `solar_clock/web/js/theme.js` | create | Colour rules copied from the TFT (Task 5) |
| `solar_clock/web/js/nav.js` | create | Index wrapping, URL hash, swipe direction (Task 5) |
| `solar_clock/web/index.html`, `style.css`, `js/app.js` | create | Page shell, layout, polling and navigation glue (Task 6) |
| `solar_clock/web/js/views/index.js` | create, then grows | Ordered view list (Tasks 6–8) |
| `solar_clock/web/js/views/{clock,weather,airquality,solar,moon}.js` | create | One view each: `render(data, now) → string` (Tasks 6–8) |
| `tools/make_icons.py`, `solar_clock/web/icons/*`, `solar_clock/web/manifest.webmanifest` | create | App icon and manifest (Task 9) |
| `tests/test_web_api.py`, `tests/test_web_page_files.py`, `tests/test_web_contract.py` | create | Python tests |
| `tests/test_weather.py`, `tests/test_http_server.py`, `tests/test_main.py` | append | New test classes only |
| `tests/web/*.mjs` | create | JS tests and fixtures |
| `.github/workflows/test.yml` | modify | Node set-up for the contract test, and a `web` job (Task 5) |
| `README.md`, `CLAUDE.md` | modify | Document the page (Task 10) |

---

### Task 1: Weather fetch lock

The TFT main loop and the page's HTTP thread will share one `WeatherProvider`. Today two threads that both find the cache expired can both fetch. This task adds one non-blocking lock per endpoint: the second caller gets the cache immediately instead of fetching again or waiting.

**Files:**
- Modify: `solar_clock/data/weather.py` (imports, `__init__`, `_fetch_weather`, `_fetch_air_quality`)
- Test: `tests/test_weather.py` (append class `TestFetchLock`, add two imports)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `WeatherProvider._fetch_weather()` and `_fetch_air_quality()` now return at once if that endpoint's fetch is already running.
  - The original bodies move to `_fetch_weather_unlocked()` and `_fetch_air_quality_unlocked()`.
  - New attributes `_weather_fetch_lock` and `_aqi_fetch_lock` (`threading.Lock`).
  - Public method behaviour is unchanged for a single thread.

- [ ] **Step 1: Write the failing tests.** Apply this change to `tests/test_weather.py`: two imports at the top, one new class at the end.

```diff
--- a/tests/test_weather.py
+++ b/tests/test_weather.py
@@ -1,4 +1,7 @@
 """Tests for weather data provider."""
+
+import threading
+import time

 import pytest
 from unittest.mock import patch, MagicMock
@@ -267,3 +270,84 @@
         assert (
             provider._weather_updated == old_updated
         ), "_weather_updated timestamp advanced despite partial failure"
+
+
+class TestFetchLock:
+    """The TFT loop and the web page's HTTP thread share one WeatherProvider."""
+
+    @pytest.fixture
+    def provider(self):
+        return WeatherProvider(api_key="test_api_key", latitude=40.7, longitude=-74.0)
+
+    @staticmethod
+    def _blocking_get(started, release, payload_for):
+        """A requests.get stand-in that holds the first fetch open until released."""
+
+        def fake_get(url, timeout=10):
+            started.set()
+            assert release.wait(timeout=5), "test never released the fetch"
+            resp = MagicMock()
+            resp.raise_for_status.return_value = None
+            resp.json.return_value = payload_for(url)
+            return resp
+
+        return fake_get
+
+    def test_concurrent_weather_fetch_hits_api_once(
+        self, provider, mock_weather_response, mock_forecast_response
+    ):
+        started, release = threading.Event(), threading.Event()
+        fake_get = self._blocking_get(
+            started,
+            release,
+            lambda url: (
+                mock_forecast_response if "forecast" in url else mock_weather_response
+            ),
+        )
+        with patch(
+            "solar_clock.data.weather.requests.get", side_effect=fake_get
+        ) as get:
+            first = threading.Thread(target=provider._fetch_weather)
+            first.start()
+            assert started.wait(timeout=5)
+
+            began = time.monotonic()
+            provider._fetch_weather()  # second caller while the first is mid-fetch
+            assert time.monotonic() - began < 0.5, "second caller waited for the first"
+
+            release.set()
+            first.join(timeout=5)
+
+        assert get.call_count == 2  # current + forecast, from the first fetch only
+        assert provider.get_current_weather().temperature == 72.5
+
+    def test_concurrent_aqi_fetch_hits_api_once(self, provider, mock_aqi_response):
+        started, release = threading.Event(), threading.Event()
+        fake_get = self._blocking_get(started, release, lambda url: mock_aqi_response)
+        with patch(
+            "solar_clock.data.weather.requests.get", side_effect=fake_get
+        ) as get:
+            first = threading.Thread(target=provider._fetch_air_quality)
+            first.start()
+            assert started.wait(timeout=5)
+
+            began = time.monotonic()
+            provider._fetch_air_quality()
+            assert time.monotonic() - began < 0.5, "second caller waited for the first"
+
+            release.set()
+            first.join(timeout=5)
+
+        assert get.call_count == 1
+        assert provider.get_air_quality() is not None
+
+    def test_lock_released_after_failed_fetch(self, provider):
+        with patch(
+            "solar_clock.data.weather.requests.get", side_effect=requests.Timeout()
+        ):
+            provider._fetch_weather()
+            provider._fetch_air_quality()
+
+        for lock in (provider._weather_fetch_lock, provider._aqi_fetch_lock):
+            assert lock.acquire(blocking=False), "lock left held after a failure"
+            lock.release()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `./venv/bin/pytest tests/test_weather.py -k TestFetchLock -v`
Expected: 3 FAILED.
- The two concurrency tests fail with `AssertionError: test never released the fetch`, about 5 s each, because the second caller starts its own fetch and blocks.
- `test_lock_released_after_failed_fetch` fails with `AttributeError: 'WeatherProvider' object has no attribute '_weather_fetch_lock'`.

- [ ] **Step 3: Implement the lock.** Apply this change to `solar_clock/data/weather.py`:

```diff
--- a/solar_clock/data/weather.py
+++ b/solar_clock/data/weather.py
@@ -1,6 +1,7 @@
 """Weather data provider using OpenWeatherMap API."""

 import logging
+import threading
 import time
 from concurrent.futures import ThreadPoolExecutor
 from dataclasses import dataclass
@@ -106,6 +107,12 @@
         self._weather_attempted: float = 0
         self._aqi_attempted: float = 0

+        # The TFT main loop and the web page's HTTP thread share this provider.
+        # One fetch per endpoint at a time: a caller that finds a fetch already
+        # running gets the cached data instead of starting a duplicate.
+        self._weather_fetch_lock = threading.Lock()
+        self._aqi_fetch_lock = threading.Lock()
+
     def get_current_weather(self) -> Optional[CurrentWeather]:
         """
         Get current weather conditions.
@@ -154,6 +161,15 @@
         return time.time() - last_attempt < self.RETRY_BACKOFF

     def _fetch_weather(self) -> None:
+        """Fetch weather unless another thread is already fetching it."""
+        if not self._weather_fetch_lock.acquire(blocking=False):
+            return
+        try:
+            self._fetch_weather_unlocked()
+        finally:
+            self._weather_fetch_lock.release()
+
+    def _fetch_weather_unlocked(self) -> None:
         """Fetch current weather and forecast from API concurrently."""
         if not self.api_key:
             logger.warning("No API key configured, skipping weather fetch")
@@ -226,6 +242,15 @@
             logger.warning(f"Failed to parse weather data: {e}")

     def _fetch_air_quality(self) -> None:
+        """Fetch air quality unless another thread is already fetching it."""
+        if not self._aqi_fetch_lock.acquire(blocking=False):
+            return
+        try:
+            self._fetch_air_quality_unlocked()
+        finally:
+            self._aqi_fetch_lock.release()
+
+    def _fetch_air_quality_unlocked(self) -> None:
         """Fetch air quality data from API."""
         if not self.api_key:
             logger.warning("No API key configured, skipping AQI fetch")
```

- [ ] **Step 4: Run the weather tests**

Run: `./venv/bin/pytest tests/test_weather.py -v`
Expected: 22 passed (19 existing + 3 new).

- [ ] **Step 5: Lint and commit**

```bash
./venv/bin/black --check solar_clock tests && ./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503 && ./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
git add solar_clock/data/weather.py tests/test_weather.py
git commit -m "Guard weather fetches with a non-blocking lock per endpoint" -m "The web page's HTTP thread will share WeatherProvider with the TFT loop; a caller that finds a fetch running now uses the cache instead of fetching again." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Web data service (`/api/now` JSON)

**Files:**
- Create: `solar_clock/web_api.py`
- Test: `tests/test_web_api.py`

**Interfaces:**
- Consumes:
  - `Config` (`solar_clock/config.py`) and the providers in `solar_clock/data`.
  - `DAY_THEME`, `NIGHT_THEME`, `Theme`, `ThemeManager` and `ThemeMode` from `solar_clock/views/theme.py`.
  - The module `solar_clock/views/colors.py`.
- Produces:
  - `WebDataService(config: Config, weather: WeatherProvider | None, theme_mode: Callable[[], ThemeMode])`.
  - `WebDataService.build_now() -> dict[str, Any]`, with exactly the shape in the spec's "Data API" section.
    - Top-level keys: `generated_at`, `location`, `units`, `theme`, `sun`, `weather`, `air_quality`, `moon`. The last five may each be `None`.
    - Datetimes are ISO strings with the configured timezone's offset; dates are `YYYY-MM-DD`.
  - Helpers: `hex_color`, `iso`, `palette` and `named_colors`.

- [ ] **Step 1: Write the failing tests** in `tests/test_web_api.py`:

```python
"""Tests for the web page's data service (GET /api/now)."""

import dataclasses
import datetime
import json
import logging
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from solar_clock.data.weather import AirQuality, CurrentWeather, DailyForecast
from solar_clock.views.theme import Theme, ThemeManager
from solar_clock.web_api import WebDataService, hex_color, iso

TOP_LEVEL = {
    "generated_at",
    "location",
    "units",
    "theme",
    "sun",
    "weather",
    "air_quality",
    "moon",
}


@pytest.fixture
def weather():
    """A shared WeatherProvider stand-in that returns the real dataclasses."""
    provider = MagicMock()
    provider.get_current_weather.return_value = CurrentWeather(
        temperature=64.5,
        feels_like=63.2,
        humidity=58,
        description="Scattered Clouds",
        wind_speed=7.4,
        wind_direction="WSW",
    )
    provider.get_forecast.return_value = [
        DailyForecast(date="2026-10-08", high_temp=66.1, low_temp=51.3, rain_chance=10)
    ]
    provider.get_air_quality.return_value = AirQuality(
        aqi=42,
        category="Good",
        pm25=10.1,
        pm10=18.4,
        o3=61.2,
        no2=12.7,
        so2=1.9,
        co=230.5,
        updated_at=1791485880.0,  # 2026-10-08 18:58 UTC = 2:58 PM in New York
    )
    return provider


@pytest.fixture
def service(sample_config, weather):
    return WebDataService(sample_config, weather=weather, theme_mode=lambda: "auto")


def test_build_now_is_json_with_every_section(service):
    data = json.loads(json.dumps(service.build_now()))
    assert set(data) == TOP_LEVEL
    assert data["location"] == {"name": "Test City", "timezone": "America/New_York"}
    assert data["units"] == "imperial"
    for section in ("theme", "sun", "weather", "air_quality", "moon"):
        assert data[section] is not None, section


def test_times_carry_the_configured_timezone(service):
    tz = ZoneInfo("America/New_York")
    data = service.build_now()
    generated = datetime.datetime.fromisoformat(data["generated_at"])
    assert generated.utcoffset() == tz.utcoffset(generated.replace(tzinfo=None))
    sunrise = datetime.datetime.fromisoformat(data["sun"]["times"]["sunrise"])
    assert sunrise.utcoffset() == tz.utcoffset(sunrise.replace(tzinfo=None))
    updated = datetime.datetime.fromisoformat(data["air_quality"]["updated_at"])
    assert data["air_quality"]["updated_at"] == "2026-10-08T14:58:00-04:00"
    assert updated.utcoffset() == datetime.timedelta(hours=-4)


def test_weather_sections_pass_values_through(service):
    data = service.build_now()
    assert data["weather"]["current"]["temperature"] == 64.5
    assert data["weather"]["current"]["description"] == "Scattered Clouds"
    assert data["weather"]["forecast"][0]["rain_chance"] == 10
    assert data["air_quality"]["aqi"] == 42
    assert data["air_quality"]["co"] == 230.5


def test_weather_and_air_quality_are_null_without_a_provider(sample_config):
    service = WebDataService(sample_config, weather=None, theme_mode=lambda: "auto")
    data = service.build_now()
    assert data["weather"] is None
    assert data["air_quality"] is None
    assert data["sun"] is not None


def test_weather_is_null_when_there_is_no_current_reading(service, weather):
    weather.get_current_weather.return_value = None
    weather.get_air_quality.return_value = None
    data = service.build_now()
    assert data["weather"] is None
    assert data["air_quality"] is None


def test_a_failing_section_is_null_and_logged(service, caplog):
    service._solar.get_sun_times = MagicMock(side_effect=RuntimeError("astral broke"))
    with caplog.at_level(logging.ERROR, logger="solar_clock.web_api"):
        data = service.build_now()
    assert data["sun"] is None
    assert data["moon"] is not None
    assert data["weather"] is not None
    assert "'sun' failed" in caplog.text


def test_moon_is_null_when_ephem_is_unavailable(service):
    service._lunar = MagicMock(available=False)
    assert service.build_now()["moon"] is None


def test_palettes_cover_every_theme_colour(service):
    theme = service.build_now()["theme"]
    fields = {f.name for f in dataclasses.fields(Theme)} - {"name"}
    assert set(theme["palettes"]["day"]) == fields
    assert set(theme["palettes"]["night"]) == fields
    assert theme["palettes"]["night"]["background"] == "#000000"
    assert theme["palettes"]["day"]["accent_sun"] == "#a06400"


def test_named_colours_include_the_header_colours(service):
    named = service.build_now()["theme"]["colors"]
    assert named["LIGHT_BLUE"] == "#87ceeb"
    assert named["ORANGE"] == "#ff8c00"
    assert named["PURPLE"] == "#9370db"
    assert named["DARK_BLUE"] == "#191970"


@pytest.mark.parametrize("mode", ["day", "night"])
def test_follows_the_clock_theme_mode_without_touching_it(sample_config, weather, mode):
    service = WebDataService(sample_config, weather=weather, theme_mode=lambda: mode)
    theme = service.build_now()["theme"]
    assert theme["mode"] == mode
    assert theme["active"] == mode
    # The clock's singleton ThemeManager is never created or changed.
    assert ThemeManager.get_instance() is None


def test_hex_color():
    assert hex_color((255, 140, 0)) == "#ff8c00"


def test_iso_refuses_naive_datetimes():
    with pytest.raises(ValueError):
        naive = datetime.datetime(2026, 10, 8, 12, 0)  # noqa: DTZ001 - on purpose
        iso(naive, ZoneInfo("UTC"))
    assert iso(None, ZoneInfo("UTC")) is None
```

- [ ] **Step 2: Run them and watch them fail**

Run: `./venv/bin/pytest tests/test_web_api.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'solar_clock.web_api'`.

- [ ] **Step 3: Implement** `solar_clock/web_api.py`:

```python
"""Data for the Solar Clock web page: the JSON behind GET /api/now.

Threading: the page is served by the single-threaded HTTPServer in
http_server.py, so one request runs at a time. That is what makes this
service's own SolarProvider and LunarProvider safe without locks
(LunarProvider moves a shared ephem.Observer on every call). Do not switch the
server to ThreadingHTTPServer without adding locking here. The TFT main loop
never touches these instances; the only provider shared with it is
WeatherProvider, which guards its own fetches.
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
from collections.abc import Callable
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .config import Config
from .data import LunarProvider, SolarProvider, WeatherProvider
from .data.solar import GoldenHour
from .views import colors
from .views.theme import DAY_THEME, NIGHT_THEME, Theme, ThemeManager, ThemeMode

logger = logging.getLogger(__name__)

# A runtime alias, so it uses Optional: Python 3.9 can't evaluate X | None.
Section = Optional[dict[str, Any]]


def hex_color(rgb: tuple[int, int, int]) -> str:
    """'#rrggbb' for an (r, g, b) tuple."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def iso(value: datetime.datetime | None, tz: datetime.tzinfo) -> str | None:
    """ISO 8601 text in the clock's timezone, or None."""
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError(f"naive datetime {value!r}: providers must return aware times")
    return value.astimezone(tz).isoformat(timespec="seconds")


def palette(theme: Theme) -> dict[str, str]:
    """Every colour field of a Theme as hex, keyed by field name."""
    return {
        key: hex_color(value)
        for key, value in dataclasses.asdict(theme).items()
        if key != "name"
    }


def named_colors() -> dict[str, str]:
    """The fixed colours exported by views/colors.py, e.g. {'PURPLE': '#9370db'}."""
    return {
        name: hex_color(value)
        for name, value in vars(colors).items()
        if name.isupper() and isinstance(value, tuple) and len(value) == 3
    }


class WebDataService:
    """Builds the JSON the web page polls. Read-only: never changes clock state."""

    def __init__(
        self,
        config: Config,
        weather: WeatherProvider | None,
        theme_mode: Callable[[], ThemeMode],
    ) -> None:
        """
        Args:
            config: Application configuration
            weather: The clock's shared WeatherProvider, or None without an API key
            theme_mode: Returns the clock's current theme mode; read, never set
        """
        loc = config.location
        self._config = config
        self._tz = ZoneInfo(loc.timezone)
        self._weather = weather
        self._theme_mode = theme_mode
        # Own instances, so the TFT's providers are never called from this thread.
        self._solar = SolarProvider(
            name=loc.name,
            region=loc.region,
            timezone=loc.timezone,
            latitude=loc.latitude,
            longitude=loc.longitude,
        )
        self._lunar = LunarProvider(
            latitude=loc.latitude, longitude=loc.longitude, timezone=loc.timezone
        )
        self._theme = ThemeManager(self._solar)  # not the singleton

    def build_now(self) -> dict[str, Any]:
        """Everything the phase 1 views need. A failing section becomes None."""
        return {
            "generated_at": datetime.datetime.now(self._tz).isoformat(
                timespec="seconds"
            ),
            "location": {
                "name": self._config.location.name,
                "timezone": self._config.location.timezone,
            },
            "units": self._config.weather.units,
            "theme": self._section("theme", self._theme_section),
            "sun": self._section("sun", self._sun_section),
            "weather": self._section("weather", self._weather_section),
            "air_quality": self._section("air_quality", self._air_quality_section),
            "moon": self._section("moon", self._moon_section),
        }

    @staticmethod
    def _section(name: str, build: Callable[[], Section]) -> Section:
        try:
            return build()
        except Exception:
            logger.exception("Web API section %r failed; sending null", name)
            return None

    def _theme_section(self) -> Section:
        mode = self._theme_mode()
        if mode != self._theme.mode:
            self._theme.set_mode(mode)  # our own instance; logs once per change
        return {
            "mode": mode,
            "active": self._theme.get_current_theme().name,
            "palettes": {"day": palette(DAY_THEME), "night": palette(NIGHT_THEME)},
            "colors": named_colors(),
        }

    def _sun_section(self) -> Section:
        times = self._solar.get_sun_times()
        if times is None:
            return None
        morning, evening = self._solar.get_golden_hour()
        position = self._solar.get_solar_position()
        next_event = self._solar.get_next_solar_event()
        return {
            "times": {
                key: iso(getattr(times, key), self._tz)
                for key in ("dawn", "sunrise", "noon", "sunset", "dusk")
            },
            "golden_hour": {
                "morning": self._span(morning),
                "evening": self._span(evening),
            },
            "position": (
                None
                if position is None
                else {
                    "elevation": round(position.elevation, 2),
                    "azimuth": round(position.azimuth, 2),
                }
            ),
            "day_length_hours": self._solar.get_day_length(),
            "day_length_change_min": self._solar.get_day_length_change(),
            "next_event": (
                None
                if next_event is None
                else {"name": next_event[0], "at": iso(next_event[1], self._tz)}
            ),
        }

    def _span(self, span: GoldenHour | None) -> Section:
        if span is None:
            return None
        return {"start": iso(span.start, self._tz), "end": iso(span.end, self._tz)}

    def _weather_section(self) -> Section:
        if self._weather is None:
            return None
        current = self._weather.get_current_weather()
        if current is None:
            return None
        forecast = self._weather.get_forecast(3) or []
        return {
            "current": dataclasses.asdict(current),
            "forecast": [dataclasses.asdict(day) for day in forecast],
        }

    def _air_quality_section(self) -> Section:
        if self._weather is None:
            return None
        aqi = self._weather.get_air_quality()
        if aqi is None:
            return None
        data = dataclasses.asdict(aqi)
        updated = datetime.datetime.fromtimestamp(aqi.updated_at, self._tz)
        data["updated_at"] = iso(updated, self._tz)
        return data

    def _moon_section(self) -> Section:
        if not self._lunar.available:
            return None
        phase = self._lunar.get_moon_phase()
        if phase is None:
            return None
        times = self._lunar.get_moon_times()
        return {
            "phase": {
                "phase": phase.phase,
                "illumination": phase.illumination,
                "phase_name": phase.phase_name,
                "next_new": phase.next_new.isoformat(),
                "next_full": phase.next_full.isoformat(),
                "days_to_new": phase.days_to_new,
                "days_to_full": phase.days_to_full,
            },
            "times": (
                None
                if times is None
                else {
                    "moonrise": iso(times.moonrise, self._tz),
                    "moonset": iso(times.moonset, self._tz),
                }
            ),
        }
```

- [ ] **Step 4: Run the tests**

Run: `./venv/bin/pytest tests/test_web_api.py -v`
Expected: 13 passed.

- [ ] **Step 5: Extra gates, lint, commit**

```bash
./venv/bin/mypy --strict --ignore-missing-imports --follow-imports=silent solar_clock/web_api.py
<scratchpad>/ruffenv/bin/ruff check --no-cache --target-version py39 solar_clock/web_api.py tests/test_web_api.py
./venv/bin/black --check solar_clock tests && ./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503 && ./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
git add solar_clock/web_api.py tests/test_web_api.py
git commit -m "Add WebDataService to build the web page's /api/now data" -m "Own sun, moon and theme instances; shares only WeatherProvider with the TFT. A failing section is logged and sent as null." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Static files and HTTP routes

**Files:**
- Create: `solar_clock/web_static.py`
- Modify: `solar_clock/http_server.py` (imports, handler class attributes, two new methods, `do_GET`, `create_server`)
- Modify: `setup.py` (`package_data`)
- Test: `tests/test_http_server.py` (append helper `_request` and class `TestWebPageRoutes`, add two imports)

**Interfaces:**
- Consumes: `WebDataService.build_now()` (Task 2).
- Produces:
  - `solar_clock.web_static`: `WEB_DIR` (the `solar_clock/web` folder), `CONTENT_TYPES`, and `StaticSite(root: Path = WEB_DIR)`.
    - `StaticSite` raises `FileNotFoundError` if `index.html` is missing.
    - `StaticSite.resolve(url_path: str) -> tuple[Path, str] | None`.
  - `create_server(config, clock_instance, web_service=None, static_site=None)`. Existing two-argument calls keep working.
  - Routes:
    - `/` and allowlisted files: 200 with `Cache-Control: no-cache`, exempt from the rate limiter.
    - `/` when `static_site` is None: 503.
    - `/api/now`: 200 JSON, 503 when `web_service` is None, 500 if building fails.
    - Any other new path: 404.
    - New routes ignore a query string.

- [ ] **Step 1: Write the failing tests.** Apply this change to `tests/test_http_server.py`:

```diff
--- a/tests/test_http_server.py
+++ b/tests/test_http_server.py
@@ -1,6 +1,7 @@
 """Tests for HTTP server and API endpoints."""

 import base64
+import json
 import os
 import time
 from io import BytesIO
@@ -15,6 +16,7 @@
     create_server,
     start_server_thread,
 )
+from solar_clock.web_static import StaticSite


 class TestRateLimiter:
@@ -426,3 +428,144 @@
         # Clean up
         server.shutdown()
         thread.join(timeout=1)
+
+
+def _request(path):
+    """Run one GET through ScreenshotHandler; return (status, headers, body)."""
+    handler = object.__new__(ScreenshotHandler)
+    handler.path = path
+    handler.headers = {}
+    handler.wfile = BytesIO()
+    handler.client_address = ("127.0.0.1", 12345)
+    handler.send_response = Mock()
+    handler.send_header = Mock()
+    handler.end_headers = Mock()
+    handler.do_GET()
+    status = handler.send_response.call_args[0][0]
+    headers = {c[0][0]: c[0][1] for c in handler.send_header.call_args_list}
+    return status, headers, handler.wfile.getvalue()
+
+
+class TestWebPageRoutes:
+    """The web page: its static files and /api/now."""
+
+    @pytest.fixture
+    def site_root(self, tmp_path):
+        root = tmp_path / "web"
+        (root / "js").mkdir(parents=True)
+        (root / "index.html").write_text("<!doctype html><title>Solar Clock</title>")
+        (root / "style.css").write_text("body {}")
+        (root / "js" / "app.js").write_text("export {};")
+        (root / "manifest.webmanifest").write_text("{}")
+        (root / "notes.txt").write_text("not on the allowlist")
+        (tmp_path / "config.json").write_text('{"secret": "coordinates"}')
+        return root
+
+    @pytest.fixture(autouse=True)
+    def web_handler(self, site_root):
+        ScreenshotHandler.clock_instance = MagicMock()
+        ScreenshotHandler.rate_limiter = None
+        ScreenshotHandler.auth_credentials = None
+        ScreenshotHandler.static_site = StaticSite(site_root)
+        ScreenshotHandler.web_service = MagicMock()
+        ScreenshotHandler.web_service.build_now.return_value = {"sun": None}
+        yield
+        ScreenshotHandler.static_site = None
+        ScreenshotHandler.web_service = None
+
+    def test_root_serves_index_html(self):
+        status, headers, body = _request("/")
+        assert status == 200
+        assert headers["Content-Type"] == "text/html; charset=utf-8"
+        assert headers["Cache-Control"] == "no-cache"
+        assert b"Solar Clock" in body
+
+    def test_root_ignores_a_query_string(self):
+        status, _, body = _request("/?from=homescreen")
+        assert status == 200
+        assert b"Solar Clock" in body
+
+    @pytest.mark.parametrize(
+        "path, content_type",
+        [
+            ("/style.css", "text/css; charset=utf-8"),
+            ("/js/app.js", "text/javascript; charset=utf-8"),
+            ("/manifest.webmanifest", "application/manifest+json"),
+        ],
+    )
+    def test_static_files_have_the_right_type(self, path, content_type):
+        status, headers, _ = _request(path)
+        assert status == 200
+        assert headers["Content-Type"] == content_type
+
+    def test_files_outside_the_allowlist_are_not_served(self):
+        status, _, _ = _request("/notes.txt")
+        assert status == 404
+
+    @pytest.mark.parametrize(
+        "path",
+        [
+            "/../config.json",
+            "/js/../../config.json",
+            "/%2e%2e/config.json",
+            "/js/%2e%2e/%2e%2e/config.json",
+            "/..%2fconfig.json",
+        ],
+    )
+    def test_traversal_attempts_get_404(self, path):
+        status, _, body = _request(path)
+        assert status == 404
+        assert b"coordinates" not in body
+
+    def test_api_now_returns_json(self):
+        status, headers, body = _request("/api/now")
+        assert status == 200
+        assert headers["Content-Type"] == "application/json"
+        assert json.loads(body) == {"sun": None}
+
+    def test_api_now_is_503_without_the_service(self):
+        ScreenshotHandler.web_service = None
+        status, _, _ = _request("/api/now")
+        assert status == 503
+
+    def test_api_now_is_500_when_building_fails(self):
+        ScreenshotHandler.web_service.build_now.side_effect = RuntimeError("boom")
+        status, _, body = _request("/api/now")
+        assert status == 500
+        assert b"boom" not in body
+
+    def test_root_is_503_when_the_page_files_failed_to_load(self):
+        ScreenshotHandler.static_site = None
+        status, _, _ = _request("/")
+        assert status == 503
+
+    def test_unknown_api_path_is_404(self):
+        status, _, _ = _request("/api/nope")
+        assert status == 404
+
+    def test_page_files_skip_the_rate_limit_but_the_api_does_not(self):
+        ScreenshotHandler.rate_limiter = RateLimiter(rate_per_second=1)
+        for _ in range(5):
+            assert _request("/style.css")[0] == 200
+        assert _request("/api/now")[0] == 200
+        assert _request("/api/now")[0] == 429
+
+    def test_existing_endpoints_still_work_alongside_the_page(self):
+        status, _, body = _request("/health")
+        assert status == 200
+        assert body == b"OK"
+
+    def test_missing_index_html_stops_the_site_loading(self, tmp_path):
+        with pytest.raises(FileNotFoundError):
+            StaticSite(tmp_path / "empty")
+
+    def test_create_server_hands_over_the_web_page(self):
+        config = MagicMock(enabled=True, port=0, bind_address="127.0.0.1")
+        config.rate_limit_per_second = 10
+        service, site = MagicMock(), MagicMock()
+        server = create_server(config, MagicMock(), service, site)
+        try:
+            assert ScreenshotHandler.web_service is service
+            assert ScreenshotHandler.static_site is site
+        finally:
+            server.server_close()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `./venv/bin/pytest tests/test_http_server.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'solar_clock.web_static'`. The whole file errors until Step 3 because of the new import.

- [ ] **Step 3: Implement.** Create `solar_clock/web_static.py`:

```python
"""The web page's static files, served only from an allowlist built at startup."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webmanifest": "application/manifest+json",
}


class StaticSite:
    """Maps URL paths to files under web/.

    The map is built once by walking the folder, so only files that existed at
    startup, with an extension in CONTENT_TYPES, can ever be served. A request
    for anything else, including '..' tricks, finds no entry.
    """

    def __init__(self, root: Path = WEB_DIR) -> None:
        index = root / "index.html"
        if not index.is_file():
            raise FileNotFoundError(f"Web page missing: {index}")
        self._files: dict[str, tuple[Path, str]] = {}
        for path in sorted(root.rglob("*")):
            content_type = CONTENT_TYPES.get(path.suffix)
            if content_type is not None and path.is_file():
                url = "/" + path.relative_to(root).as_posix()
                self._files[url.lower()] = (path, content_type)
        logger.info(f"Web page: {len(self._files)} files from {root}")

    def resolve(self, url_path: str) -> tuple[Path, str] | None:
        """(file, content type) for a request path, or None if it isn't served."""
        path = url_path.split("?", 1)[0].lower()
        if path == "/":
            path = "/index.html"
        return self._files.get(path)
```

Apply this change to `solar_clock/http_server.py`:

```diff
--- a/solar_clock/http_server.py
+++ b/solar_clock/http_server.py
@@ -8,10 +8,13 @@
 import time
 from http.server import HTTPServer, BaseHTTPRequestHandler
 from io import BytesIO
+from pathlib import Path
 from typing import TYPE_CHECKING, Optional

 if TYPE_CHECKING:
     from .config import HttpServerConfig
+    from .web_api import WebDataService
+    from .web_static import StaticSite

 logger = logging.getLogger(__name__)

@@ -42,15 +45,18 @@
 class ScreenshotHandler(BaseHTTPRequestHandler):
     """HTTP request handler for screenshots and navigation.

-    Note: clock_instance, rate_limiter, and auth_credentials are stored as
-    class variables (required by BaseHTTPRequestHandler's design). This means
-    only one server configuration can exist at a time.
+    Note: clock_instance, rate_limiter, auth_credentials, web_service and
+    static_site are stored as class variables (required by
+    BaseHTTPRequestHandler's design). This means only one server configuration
+    can exist at a time.
     """

     # Class-level references (set by create_server)
     clock_instance = None
     rate_limiter: Optional[RateLimiter] = None
     auth_credentials: Optional[tuple[str, str]] = None  # (user, pass)
+    web_service: Optional["WebDataService"] = None  # None: page unavailable
+    static_site: Optional["StaticSite"] = None  # None: page unavailable

     def log_message(self, format: str, *args) -> None:
         """Override to use proper logging."""
@@ -111,6 +117,34 @@
         self.send_header("Cache-Control", "no-cache")
         self.end_headers()
         self.wfile.write(image_data)
+
+    def _send_static_file(self, file_path: Path, content_type: str) -> None:
+        """Send one of the web page's files."""
+        try:
+            body = file_path.read_bytes()
+        except OSError as e:
+            logger.error(f"Could not read {file_path}: {e}")
+            self._send_text(500, "Error reading file")
+            return
+        self.send_response(200)
+        self.send_header("Content-Type", content_type)
+        self.send_header("Content-Length", str(len(body)))
+        self.send_header("Cache-Control", "no-cache")
+        self.end_headers()
+        self.wfile.write(body)
+
+    def _send_api_now(self) -> None:
+        """Send the web page's data. Read-only: never changes clock state."""
+        if self.web_service is None:
+            self._send_text(503, "Web page not available")
+            return
+        try:
+            data = self.web_service.build_now()
+        except Exception:
+            logger.exception("/api/now failed")
+            self._send_json(500, {"error": "internal error"})
+            return
+        self._send_json(200, data)

     def _require_clock(self) -> bool:
         """Check that clock_instance is available. Sends 503 if not.
@@ -137,8 +171,13 @@

     def do_GET(self) -> None:
         """Handle GET requests."""
-        # Rate limiting
-        if self.rate_limiter and not self.rate_limiter.allow():
+        path = self.path.lower()
+        route = path.split("?", 1)[0]  # new web page routes ignore query strings
+        static = self.static_site.resolve(path) if self.static_site else None
+
+        # Rate limiting. The page's own files are exempt: one page load
+        # fetches about a dozen of them at once.
+        if static is None and self.rate_limiter and not self.rate_limiter.allow():
             self._send_rate_limited()
             return

@@ -147,7 +186,9 @@
             self._send_unauthorized()
             return

-        path = self.path.lower()
+        if static is not None:
+            self._send_static_file(*static)
+            return

         if path == "/health":
             self._send_text(200, "OK")
@@ -211,6 +252,13 @@
             else:
                 self._send_text(404, "Not Found")

+        elif route == "/":
+            # Only reached when the page's files failed to load at startup.
+            self._send_text(503, "Web page not available")
+
+        elif route == "/api/now":
+            self._send_api_now()
+
         else:
             self._send_text(404, "Not Found")

@@ -218,6 +266,8 @@
 def create_server(
     config: "HttpServerConfig",
     clock_instance,
+    web_service: Optional["WebDataService"] = None,
+    static_site: Optional["StaticSite"] = None,
 ) -> Optional[HTTPServer]:
     """
     Create and configure the HTTP server.
@@ -225,6 +275,8 @@
     Args:
         config: HTTP server configuration
         clock_instance: Reference to main clock instance
+        web_service: Data for the web page; None serves 503 on /api/now
+        static_site: The web page's files; None serves 503 on /

     Returns:
         Configured HTTPServer, or None if disabled
@@ -236,6 +288,8 @@
     # Set up handler class attributes
     ScreenshotHandler.clock_instance = clock_instance
     ScreenshotHandler.rate_limiter = RateLimiter(config.rate_limit_per_second)
+    ScreenshotHandler.web_service = web_service
+    ScreenshotHandler.static_site = static_site

     # Check for auth credentials in environment
     auth_user = os.environ.get("HTTP_AUTH_USER")
```

Apply this change to `setup.py`, so an installed package carries the page:

```diff
--- a/setup.py
+++ b/setup.py
@@ -16,6 +16,16 @@
     long_description_content_type="text/markdown",
     url="https://github.com/bigguy6883/Solar-Smart-Clock",
     packages=find_packages(exclude=["tests", "tests.*"]),
+    package_data={
+        "solar_clock": [
+            "web/*.html",
+            "web/*.css",
+            "web/*.webmanifest",
+            "web/icons/*",
+            "web/js/*.js",
+            "web/js/views/*.js",
+        ]
+    },
     python_requires=">=3.9",
     install_requires=[
         "Pillow>=10.0.0",
```

- [ ] **Step 4: Run the tests**

Run: `./venv/bin/pytest tests/test_http_server.py -v`
Expected: 43 passed (23 existing + 20 new).

- [ ] **Step 5: Extra gates, lint, commit**

```bash
./venv/bin/mypy --strict --ignore-missing-imports --follow-imports=silent solar_clock/web_static.py
<scratchpad>/ruffenv/bin/ruff check --no-cache --target-version py39 solar_clock/web_static.py
./venv/bin/black --check solar_clock tests && ./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503 && ./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
git add solar_clock/web_static.py solar_clock/http_server.py setup.py tests/test_http_server.py
git commit -m "Serve the web page's files and /api/now from the HTTP server" -m "Files come only from an allowlist built at startup and skip the rate limit; /api/now is read-only. Existing endpoints are unchanged." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Wire the page into the clock, and the homelab preview

**Files:**
- Modify: `solar_clock/main.py` (two imports; a guarded block in `SolarClock.__init__` before "Initialize HTTP server"; the `create_server` call). Do not touch `run()`.
- Create: `tools/web_preview.py`
- Test: `tests/test_main.py` (append class `TestWebPageWiring`, add two imports)

**Interfaces:**
- Consumes: `WebDataService` (Task 2); `StaticSite` and the 4-argument `create_server` (Task 3).
- Produces:
  - `SolarClock` passes `(config.http_server, self, web_service, static_site)` to `create_server`. Both web objects are `None` if either fails to build; the clock still starts.
  - The preview tool runs as `./venv/bin/python -m tools.web_preview --config FILE [--port 8091] [--bind ADDR] [--theme auto|day|night] [--sample-weather]`.

- [ ] **Step 1: Write the failing tests.** Apply this change to `tests/test_main.py`:

```diff
--- a/tests/test_main.py
+++ b/tests/test_main.py
@@ -1,6 +1,7 @@
 """Tests for main application lifecycle and SolarClock class."""

 import signal
+from contextlib import ExitStack
 from pathlib import Path
 from unittest.mock import MagicMock, patch

@@ -8,6 +9,7 @@
 from PIL import Image

 from solar_clock.main import SolarClock, main
+from solar_clock.web_api import WebDataService


 class TestSolarClock:
@@ -466,3 +468,60 @@
         f"view_changed.clear() (pos {clear_pos}) must come before "
         f"view_changed.wait() (pos {wait_pos}) in run()"
     )
+
+
+class TestWebPageWiring:
+    """SolarClock hands the web page to the HTTP server without risking the clock."""
+
+    @staticmethod
+    def _build(config, *extra_patches):
+        """Construct SolarClock with hardware mocked; return (clock, create_server mock)."""
+        with ExitStack() as stack:
+            stack.enter_context(
+                patch("solar_clock.main.get_api_key", return_value=None)
+            )
+            stack.enter_context(patch("solar_clock.main.VIEW_CLASSES", []))
+            stack.enter_context(patch("solar_clock.main.ViewManager"))
+            stack.enter_context(patch("solar_clock.main.Display"))
+            stack.enter_context(patch("solar_clock.main.TouchHandler"))
+            create_server = stack.enter_context(patch("solar_clock.main.create_server"))
+            for extra in extra_patches:
+                stack.enter_context(extra)
+            clock = SolarClock(config)
+        return clock, create_server
+
+    def test_server_receives_web_service_and_site(self, sample_config):
+        clock, create_server = self._build(
+            sample_config, patch("solar_clock.main.StaticSite")
+        )
+        args = create_server.call_args[0]
+        assert args[0] is sample_config.http_server
+        assert args[1] is clock
+        assert isinstance(args[2], WebDataService)
+        assert args[3] is not None
+
+    def test_web_failure_does_not_stop_the_clock(self, sample_config, caplog):
+        clock, create_server = self._build(
+            sample_config,
+            patch("solar_clock.main.WebDataService", side_effect=RuntimeError("boom")),
+        )
+        assert clock.view_manager is not None
+        assert create_server.call_args[0][2:] == (None, None)
+        assert "Web page disabled" in caplog.text
+
+    def test_missing_page_files_disable_the_page(self, sample_config):
+        _, create_server = self._build(
+            sample_config,
+            patch("solar_clock.main.StaticSite", side_effect=FileNotFoundError("gone")),
+        )
+        assert create_server.call_args[0][2:] == (None, None)
+
+    def test_web_page_follows_the_clock_theme_mode(self, sample_config):
+        clock, create_server = self._build(
+            sample_config, patch("solar_clock.main.StaticSite")
+        )
+        web_service = create_server.call_args[0][2]
+        clock.theme_manager.set_mode("night")
+        assert web_service.build_now()["theme"]["active"] == "night"
+        clock.theme_manager.set_mode("day")
+        assert web_service.build_now()["theme"]["active"] == "day"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `./venv/bin/pytest tests/test_main.py -k TestWebPageWiring -v`
Expected: 4 FAILED, with `AttributeError: <module 'solar_clock.main' …> does not have the attribute 'StaticSite'` or `'WebDataService'`.

- [ ] **Step 3: Implement.** Apply this change to `solar_clock/main.py`:

```diff
--- a/solar_clock/main.py
+++ b/solar_clock/main.py
@@ -18,6 +18,8 @@
 from .views import VIEW_CLASSES, ViewManager
 from .views.base import DataProviders
 from .views.theme import ThemeManager
+from .web_api import WebDataService
+from .web_static import StaticSite

 # Configure logging
 logging.basicConfig(
@@ -90,8 +92,25 @@
         # Initialize display
         self.display = Display(config.display)

+        # Web page data and files. A failure here must never stop the clock.
+        web_service: Optional[WebDataService] = None
+        static_site: Optional[StaticSite] = None
+        try:
+            web_service = WebDataService(
+                config,
+                weather=self.providers.weather,
+                theme_mode=lambda: self.theme_manager.mode,
+            )
+            static_site = StaticSite()
+        except Exception:
+            logger.exception("Web page disabled")
+            web_service = None
+            static_site = None
+
         # Initialize HTTP server
-        self.http_server = create_server(config.http_server, self)
+        self.http_server = create_server(
+            config.http_server, self, web_service, static_site
+        )
         self.http_thread: Optional[threading.Thread] = None

         # Initialize touch handler
```

Create `tools/web_preview.py`:

```python
"""Serve the Solar Clock web page on homelab, without a display.

Runs only the HTTP server and the page's data service, so the page can be
built and checked from a phone before anything is deployed to clock.local.
The TFT endpoints (/screenshot, /next, ...) answer 503 here: there is no clock.

    ./venv/bin/python -m tools.web_preview --config config.example.json --port 8091

Weather needs OPENWEATHER_API_KEY in the environment; without it, pass
--sample-weather to fill the weather views with fixed example data.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from solar_clock.config import get_api_key, load_config
from solar_clock.data import WeatherProvider
from solar_clock.data.weather import (
    AirQuality,
    CurrentWeather,
    DailyForecast,
)
from solar_clock.http_server import create_server
from solar_clock.web_api import WebDataService
from solar_clock.web_static import StaticSite


class SampleWeather(WeatherProvider):
    """Fixed example weather, so the views can be checked without an API key."""

    def __init__(self) -> None:
        super().__init__(api_key="", latitude=0.0, longitude=0.0)

    def get_current_weather(self) -> CurrentWeather | None:
        return CurrentWeather(
            temperature=64.5,
            feels_like=63.2,
            humidity=58,
            description="Scattered Clouds",
            wind_speed=7.4,
            wind_direction="WSW",
        )

    def get_forecast(self, days: int = 3) -> list[DailyForecast] | None:
        today = time.strftime("%Y-%m-%d")
        return [
            DailyForecast(date=today, high_temp=66.1, low_temp=51.3, rain_chance=10),
            DailyForecast(date=today, high_temp=61.0, low_temp=48.8, rain_chance=40),
            DailyForecast(date=today, high_temp=58.4, low_temp=45.0, rain_chance=0),
        ][:days]

    def get_air_quality(self) -> AirQuality | None:
        return AirQuality(
            aqi=42,
            category="Good",
            pm25=10.1,
            pm10=18.4,
            o3=61.2,
            no2=12.7,
            so2=1.9,
            co=230.5,
            updated_at=time.time(),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Serve the web page without a display."
    )
    parser.add_argument("--config", type=Path, required=True, help="config.json to use")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--bind", default="0.0.0.0", help="address to listen on")
    parser.add_argument(
        "--theme", choices=["auto", "day", "night"], help="override the theme mode"
    )
    parser.add_argument(
        "--sample-weather", action="store_true", help="use fixed example weather"
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    config = load_config(args.config)
    config.http_server.enabled = True
    config.http_server.port = args.port
    config.http_server.bind_address = args.bind

    api_key = get_api_key()
    weather: WeatherProvider | None = None
    if args.sample_weather:
        weather = SampleWeather()
    elif api_key:
        weather = WeatherProvider(
            api_key=api_key,
            latitude=config.location.latitude,
            longitude=config.location.longitude,
            units=config.weather.units,
            weather_interval=config.weather.update_interval_seconds,
            aqi_interval=config.air_quality.update_interval_seconds,
        )

    mode = args.theme or config.appearance.theme_mode
    service = WebDataService(config, weather=weather, theme_mode=lambda: mode)
    server = create_server(config.http_server, None, service, StaticSite())
    if server is None:
        raise RuntimeError("HTTP server is disabled")  # enabled is forced on above
    print(f"Serving the web page on port {args.port}. Ctrl+C stops it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `./venv/bin/pytest tests/test_main.py -v`, then `./venv/bin/pytest`
Expected: 28 passed in `test_main.py`, then the full suite 299 passed, 3 skipped. `test_web_page_files.py` and `test_web_contract.py` don't exist yet.

While `solar_clock/web/index.html` does not exist (until Task 6), `SolarClock` logs `Web page disabled` during these tests. That is the guard working.

- [ ] **Step 5: Smoke-test the preview tool.** Check the port is free first (memory rule: never kill a port without looking).

```bash
ss -tlnp | grep ":8091 " || echo "8091 free"
./venv/bin/python -m tools.web_preview --config config.example.json --port 8091 --bind 127.0.0.1 --sample-weather > <scratchpad>/preview.log 2>&1 &
echo $! > <scratchpad>/preview.pid
# wait until it answers, up to ~10 s
timeout 10 bash -c 'until curl -sf http://127.0.0.1:8091/health >/dev/null; do sleep 0.5; done'
curl -s -o /dev/null -w "/api/now %{http_code}\n" http://127.0.0.1:8091/api/now
curl -s -o /dev/null -w "/ %{http_code}\n" http://127.0.0.1:8091/
kill "$(cat <scratchpad>/preview.pid)"
```

Expected: `/api/now 200`, and `/ 503` because the page files don't exist until Task 6. Stop the server by its saved PID. Do not use `pkill -f` with a pattern: it matches your own shell's command line and kills it.

- [ ] **Step 6: Extra gates, lint, commit**

```bash
./venv/bin/mypy --strict --ignore-missing-imports --follow-imports=silent tools/web_preview.py
<scratchpad>/ruffenv/bin/ruff check --no-cache --target-version py39 tools/web_preview.py
./venv/bin/black --check solar_clock tests tools/web_preview.py && ./venv/bin/flake8 solar_clock tests tools/web_preview.py --max-line-length=100 --ignore=E501,W503 && ./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
git add solar_clock/main.py tools/web_preview.py tests/test_main.py
git commit -m "Hand the web page to the HTTP server; add a homelab preview" -m "A failure building the page is logged and the clock runs without it. tools/web_preview.py serves the page without a display." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Page foundations: formatting, colour and navigation helpers

These pure functions copy the TFT's text formats and colour rules, so views stay small and testable without a browser.

**Files:**
- Create: `solar_clock/web/package.json`, `solar_clock/web/js/format.js`, `solar_clock/web/js/theme.js`, `solar_clock/web/js/nav.js`
- Create: `tests/web/fixtures.mjs`, `tests/web/format.test.mjs`, `tests/web/theme.test.mjs`, `tests/web/nav.test.mjs`
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: the `/api/now` shape (Task 2). `tests/web/fixtures.mjs` is a realistic sample of it.
- Produces:
  - `format.js`: `zoned`, `time12`, `time12Bare`, `clockParts`, `longDate`, `shortDate`, `weekdayShort`, `hoursMinutes`, `dayLengthPadded`, `dayLengthText`, `countdownHM`, `dayFraction`, `compass8`, `fixed` and `escapeHtml`.
  - `theme.js`: `namedColors(data)`, `cssVariables(palette)`, `timeOfDayHeader(now, sun, colors, tz)`, `aqiHeaderColor`, `aqiTextColor` and `pollutantBarColor`.
  - `nav.js`: `SWIPE_MIN_PX`, `wrapIndex`, `indexFromHash` and `swipeDelta`. A swipe right (finger moves left to right) means next view, the same direction as the TFT (`touch_handler.py`: `dx > 0` is next). Peter chose this on 2026-10-08.
  - `fixtures.mjs`: `TZ`, `NOW` (Thu 8 Oct 2026, 3:12 PM New York), `sampleNow()`, `HOSTILE` and `assertShows`.

- [ ] **Step 1: Write the fixtures and failing tests**

`solar_clock/web/package.json` lets Node load the page's `.js` files as ES modules. It has no extension the server serves, so it is never sent to browsers.

```json
{
  "private": true,
  "type": "module"
}
```

`tests/web/fixtures.mjs`:

```js
// A realistic /api/now response for the view tests: Thursday 8 Oct 2026,
// 3:12 PM in New York, night theme. Edit copies, never this object.

import assert from "node:assert/strict";

export const TZ = "America/New_York";
export const NOW = new Date("2026-10-08T15:12:00-04:00");

const SAMPLE = {
  generated_at: "2026-10-08T15:12:00-04:00",
  location: { name: "Test City", timezone: TZ },
  units: "imperial",
  theme: {
    mode: "auto",
    active: "night",
    palettes: {
      day: {
        background: "#f5f3eb", background_panel: "#e6e4dc", background_panel_dark: "#dcdad2",
        text_primary: "#1e1e1e", text_secondary: "#505050", text_tertiary: "#787878",
        nav_background: "#ebe9e1", nav_button: "#c8c6be", nav_dot_active: "#1e1e1e",
        nav_dot_inactive: "#a0a0a0", clock_face: "#fffffa", clock_hands: "#1e1e1e",
        clock_markers: "#505050", divider: "#c8c6be", outline: "#b4b2aa",
        accent_sun: "#a06400", accent_warm: "#b44600", accent_moon: "#7d5f0a",
        accent_cool: "#1e5ab4", accent_green: "#147328",
      },
      night: {
        background: "#000000", background_panel: "#232328", background_panel_dark: "#191e19",
        text_primary: "#ffffff", text_secondary: "#b4b4b4", text_tertiary: "#808080",
        nav_background: "#000000", nav_button: "#3c3c3c", nav_dot_active: "#ffffff",
        nav_dot_inactive: "#808080", clock_face: "#f0f0e6", clock_hands: "#000000",
        clock_markers: "#323232", divider: "#282832", outline: "#808080",
        accent_sun: "#ffdc32", accent_warm: "#ff961e", accent_moon: "#fff8dc",
        accent_cool: "#6495ed", accent_green: "#00c800",
      },
    },
    colors: {
      BLACK: "#000000", WHITE: "#ffffff", YELLOW: "#ffdc32", ORANGE: "#ff8c00",
      BLUE: "#6495ed", DARK_BLUE: "#191970", LIGHT_BLUE: "#87ceeb", GRAY: "#808080",
      LIGHT_GRAY: "#b4b4b4", DARK_GRAY: "#323232", RED: "#ff5050", PURPLE: "#9370db",
      GREEN: "#00c800", MOON_YELLOW: "#fff8dc", AQI_GOOD: "#00e400", AQI_MODERATE: "#ffff00",
      AQI_UNHEALTHY_SENSITIVE: "#ff7e00", AQI_UNHEALTHY: "#ff0000",
      AQI_VERY_UNHEALTHY: "#8f3f97", AQI_HAZARDOUS: "#7e0023",
      NAV_BUTTON_COLOR: "#3c3c3c", NAV_BUTTON_ACTIVE: "#505050",
    },
  },
  sun: {
    times: {
      dawn: "2026-10-08T06:42:00-04:00",
      sunrise: "2026-10-08T07:08:00-04:00",
      noon: "2026-10-08T12:52:00-04:00",
      sunset: "2026-10-08T18:35:00-04:00",
      dusk: "2026-10-08T19:01:00-04:00",
    },
    golden_hour: {
      morning: { start: "2026-10-08T06:52:00-04:00", end: "2026-10-08T07:47:00-04:00" },
      evening: { start: "2026-10-08T17:56:00-04:00", end: "2026-10-08T18:51:00-04:00" },
    },
    position: { elevation: 31.42, azimuth: 222.6 },
    day_length_hours: 11.5,
    day_length_change_min: -2.13,
    next_event: { name: "Sunset", at: "2026-10-08T18:35:00-04:00" },
  },
  weather: {
    current: {
      temperature: 64.5, feels_like: 63.2, humidity: 58,
      description: "Scattered Clouds", wind_speed: 7.4, wind_direction: "WSW",
    },
    forecast: [
      { date: "2026-10-08", high_temp: 66.1, low_temp: 51.3, rain_chance: 10 },
      { date: "2026-10-09", high_temp: 61.0, low_temp: 48.8, rain_chance: 40 },
      { date: "2026-10-10", high_temp: 58.4, low_temp: 45.0, rain_chance: 0 },
    ],
  },
  air_quality: {
    aqi: 42, category: "Good", pm25: 10.1, pm10: 18.4, o3: 61.2, no2: 12.7, so2: 1.9,
    co: 230.5, updated_at: "2026-10-08T14:58:00-04:00",
  },
  moon: {
    phase: {
      phase: 0.89, illumination: 14.2, phase_name: "Waning Crescent",
      next_new: "2026-10-10", next_full: "2026-10-26", days_to_new: 2, days_to_full: 18,
    },
    times: { moonrise: "2026-10-08T03:41:00-04:00", moonset: "2026-10-08T17:20:00-04:00" },
  },
};

/** A fresh copy of the sample, safe to modify in a test. */
export function sampleNow() {
  return structuredClone(SAMPLE);
}

/** Every string that must never reach the page unescaped. */
export const HOSTILE = '<img src=x onerror="alert(1)">';

/** Fail unless every string in `expected` appears in `html`. */
export function assertShows(html, expected) {
  for (const text of expected) assert.ok(html.includes(text), `missing: ${text}`);
}
```

`tests/web/format.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  clockParts, compass8, countdownHM, dayFraction, dayLengthPadded, dayLengthText,
  escapeHtml, fixed, longDate, shortDate, time12, time12Bare, weekdayShort, zoned,
} from "../../solar_clock/web/js/format.js";
import { NOW, TZ } from "./fixtures.mjs";

test("times are shown in the clock's timezone, not the viewer's", () => {
  assert.equal(time12("2026-10-08T07:08:00-04:00", TZ), "7:08 AM");
  assert.equal(time12("2026-10-08T07:08:00-04:00", "Asia/Tokyo"), "8:08 PM");
  assert.equal(zoned(NOW, TZ).hour, 15);
});

test("12-hour times match %-I:%M %p, including midnight and noon", () => {
  assert.equal(time12("2026-10-08T00:05:00-04:00", TZ), "12:05 AM");
  assert.equal(time12("2026-10-08T12:00:00-04:00", TZ), "12:00 PM");
  assert.equal(time12("2026-10-08T18:35:00-04:00", TZ), "6:35 PM");
  assert.equal(time12Bare("2026-10-08T17:56:00-04:00", TZ), "5:56");
});

test("clock header and long date match the TFT", () => {
  assert.deepEqual(clockParts(NOW, TZ), { time: "3:12:00", ampm: "PM" });
  assert.equal(longDate(NOW, TZ), "Thursday, October 08, 2026");
});

test("date-only strings format without timezone shifts", () => {
  assert.equal(shortDate("2026-10-10"), "Oct 10");
  assert.equal(shortDate("2026-01-06"), "Jan 06");
  assert.equal(weekdayShort("2026-10-10"), "Sat");
});

test("day lengths truncate minutes like Python int()", () => {
  assert.equal(dayLengthPadded(11.5), "11h 30m");
  assert.equal(dayLengthPadded(9.0834), "9h 05m");
  assert.equal(dayLengthText(9.0834), "9h 5m");
});

test("countdown is hours and minutes and stops at zero", () => {
  assert.deepEqual(countdownHM("2026-10-08T18:35:00-04:00", NOW), { h: 3, m: 23 });
  assert.deepEqual(countdownHM("2026-10-08T15:00:00-04:00", NOW), { h: 0, m: 0 });
});

test("day fraction uses the clock's local midnight", () => {
  assert.equal(fixed(dayFraction(NOW, TZ) * 100), "63");
});

test("compass names match ClockView", () => {
  assert.equal(compass8(0), "N");
  assert.equal(compass8(222.6), "SW");
  assert.equal(compass8(337.5), "N");
  assert.equal(compass8(300), "NW");
});

test("fixed() rounds like Python format()", () => {
  const cases = [
    [64.5, 0, "64"], [65.5, 0, "66"], [2.25, 1, "2.2"], [2.75, 1, "2.8"],
    [0.15, 1, "0.1"], [-2.5, 0, "-2"], [-0.4, 0, "-0"], [-0.04, 1, "-0.0"],
    [31.42, 1, "31.4"], [222.6, 0, "223"],
  ];
  for (const [value, digits, expected] of cases) {
    assert.equal(fixed(value, digits), expected, `fixed(${value}, ${digits})`);
  }
});

test("escapeHtml neutralises markup", () => {
  assert.equal(escapeHtml(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
});
```

`tests/web/theme.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  aqiHeaderColor, aqiTextColor, cssVariables, namedColors, pollutantBarColor, timeOfDayHeader,
} from "../../solar_clock/web/js/theme.js";
import { NOW, TZ, sampleNow } from "./fixtures.mjs";

const data = sampleNow();
const colors = namedColors(data);
const at = (time) => new Date(`2026-10-08T${time}:00-04:00`);

test("header colour follows the sun like BaseView.get_time_header_color", () => {
  assert.equal(timeOfDayHeader(at("06:00"), data.sun, colors, TZ), colors.DARK_BLUE);
  assert.equal(timeOfDayHeader(at("06:50"), data.sun, colors, TZ), colors.ORANGE);
  assert.equal(timeOfDayHeader(NOW, data.sun, colors, TZ), colors.LIGHT_BLUE);
  assert.equal(timeOfDayHeader(at("18:45"), data.sun, colors, TZ), colors.ORANGE);
  assert.equal(timeOfDayHeader(at("21:00"), data.sun, colors, TZ), colors.PURPLE);
});

test("header colour falls back to fixed hours without sun data", () => {
  assert.equal(timeOfDayHeader(at("05:00"), null, colors, TZ), colors.DARK_BLUE);
  assert.equal(timeOfDayHeader(at("07:30"), null, colors, TZ), colors.ORANGE);
  assert.equal(timeOfDayHeader(at("16:59"), null, colors, TZ), colors.LIGHT_BLUE);
  assert.equal(timeOfDayHeader(at("19:00"), null, colors, TZ), colors.ORANGE);
  assert.equal(timeOfDayHeader(at("20:00"), null, colors, TZ), colors.PURPLE);
});

test("AQI colours match AirQualityView", () => {
  assert.equal(aqiHeaderColor(42, colors), "#00822d");
  assert.equal(aqiHeaderColor(250, colors), colors.AQI_VERY_UNHEALTHY);
  assert.equal(aqiTextColor(42, "night", colors), colors.AQI_GOOD);
  assert.equal(aqiTextColor(80, "night", colors), "#c8b400");
  assert.equal(aqiTextColor(80, "day", colors), "#aa8200");
  assert.equal(aqiTextColor(400, "night", colors), colors.AQI_HAZARDOUS);
});

test("pollutant bars change colour at half and three-quarters full", () => {
  assert.equal(pollutantBarColor(0.49, colors), colors.AQI_GOOD);
  assert.equal(pollutantBarColor(0.5, colors), colors.AQI_MODERATE);
  assert.equal(pollutantBarColor(0.75, colors), colors.AQI_UNHEALTHY);
});

test("palette keys become CSS variables", () => {
  const vars = new Map(cssVariables(data.theme.palettes.night));
  assert.equal(vars.get("--background-panel-dark"), "#191e19");
  assert.equal(vars.get("--accent-sun"), "#ffdc32");
  assert.equal(vars.size, 20);
});
```

`tests/web/nav.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { indexFromHash, swipeDelta, wrapIndex } from "../../solar_clock/web/js/nav.js";

test("navigation wraps at both ends", () => {
  assert.equal(wrapIndex(4, 1, 5), 0);
  assert.equal(wrapIndex(0, -1, 5), 4);
  assert.equal(wrapIndex(2, 1, 5), 3);
});

test("the URL hash picks the view, defaulting to Clock", () => {
  const names = ["clock", "weather", "moon"];
  assert.equal(indexFromHash("#moon", names), 2);
  assert.equal(indexFromHash("#MOON", names), 2);
  assert.equal(indexFromHash("", names), 0);
  assert.equal(indexFromHash("#nope", names), 0);
});

test("a clear horizontal swipe moves one view; anything else is ignored", () => {
  assert.equal(swipeDelta(80, 10), 1); // right = next, as on the TFT
  assert.equal(swipeDelta(-80, 10), -1);
  assert.equal(swipeDelta(30, 0), 0);
  assert.equal(swipeDelta(80, 120), 0);
});
```

- [ ] **Step 2: Run them and watch them fail**

Run: `node --test tests/web/*.test.mjs`
Expected: 3 failing files with `ERR_MODULE_NOT_FOUND` for `format.js`, `theme.js` and `nav.js`.

- [ ] **Step 3: Implement.** `solar_clock/web/js/format.js`:

```js
// Text formatting that matches the TFT's strftime patterns. Times are shown in
// the clock's configured timezone, not the viewer's.

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const WEEKDAYS_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const formatters = new Map();

function formatterFor(timeZone) {
  let formatter = formatters.get(timeZone);
  if (formatter === undefined) {
    formatter = new Intl.DateTimeFormat("en-US", {
      timeZone,
      hourCycle: "h23",
      weekday: "long",
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
    });
    formatters.set(timeZone, formatter);
  }
  return formatter;
}

function toDate(value) {
  return value instanceof Date ? value : new Date(value);
}

const pad2 = (n) => String(n).padStart(2, "0");
const hour12 = (hour) => hour % 12 || 12;

/** Wall-clock fields of an instant (Date or ISO string) in `timeZone`. */
export function zoned(value, timeZone) {
  const parts = {};
  for (const part of formatterFor(timeZone).formatToParts(toDate(value))) {
    parts[part.type] = part.value;
  }
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour) % 24,
    minute: Number(parts.minute),
    second: Number(parts.second),
    weekday: parts.weekday,
  };
}

/** "%-I:%M %p", e.g. "6:42 AM". */
export function time12(value, timeZone) {
  const z = zoned(value, timeZone);
  return `${hour12(z.hour)}:${pad2(z.minute)} ${z.hour < 12 ? "AM" : "PM"}`;
}

/** "%-I:%M", e.g. "6:42" (the start of a golden-hour range). */
export function time12Bare(value, timeZone) {
  const z = zoned(value, timeZone);
  return `${hour12(z.hour)}:${pad2(z.minute)}`;
}

/** Clock header: "%-I:%M:%S" and "%p". */
export function clockParts(now, timeZone) {
  const z = zoned(now, timeZone);
  return {
    time: `${hour12(z.hour)}:${pad2(z.minute)}:${pad2(z.second)}`,
    ampm: z.hour < 12 ? "AM" : "PM",
  };
}

/** "%A, %B %d, %Y", e.g. "Thursday, October 08, 2026". */
export function longDate(now, timeZone) {
  const z = zoned(now, timeZone);
  return `${z.weekday}, ${MONTHS[z.month - 1]} ${pad2(z.day)}, ${z.year}`;
}

/** "%b %d" for a "YYYY-MM-DD" date, e.g. "Oct 10". */
export function shortDate(isoDate) {
  const [, month, day] = isoDate.split("-").map(Number);
  return `${MONTHS[month - 1].slice(0, 3)} ${pad2(day)}`;
}

/** "%a" for a "YYYY-MM-DD" date, e.g. "Sat". */
export function weekdayShort(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return WEEKDAYS_SHORT[new Date(Date.UTC(year, month - 1, day)).getUTCDay()];
}

/** Whole hours and minutes, truncated like Python's int(). */
export function hoursMinutes(hours) {
  const h = Math.trunc(hours);
  return { h, m: Math.trunc((hours - h) * 60) };
}

/** Clock view day length, e.g. "11h 05m". */
export function dayLengthPadded(hours) {
  const { h, m } = hoursMinutes(hours);
  return `${h}h ${pad2(m)}m`;
}

/** Solar view day length, e.g. "11h 5m". */
export function dayLengthText(hours) {
  const { h, m } = hoursMinutes(hours);
  return `${h}h ${m}m`;
}

/** Hours and minutes from `now` until `target`; zero once it has passed. */
export function countdownHM(target, now) {
  const seconds = Math.max(0, (toDate(target) - toDate(now)) / 1000);
  return { h: Math.floor(seconds / 3600), m: Math.floor((seconds % 3600) / 60) };
}

/** Fraction (0-1) of the local day that has passed at `now`. */
export function dayFraction(now, timeZone) {
  const z = zoned(now, timeZone);
  return (z.hour * 3600 + z.minute * 60 + z.second) / 86400;
}

/** 8-point compass name for an azimuth in degrees (as ClockView). */
export function compass8(azimuth) {
  if (azimuth >= 337.5 || azimuth < 22.5) return "N";
  if (azimuth < 67.5) return "NE";
  if (azimuth < 112.5) return "E";
  if (azimuth < 157.5) return "SE";
  if (azimuth < 202.5) return "S";
  if (azimuth < 247.5) return "SW";
  if (azimuth < 292.5) return "W";
  return "NW";
}

/**
 * Python's format(value, ".Nf"). toFixed rounds exact halves away from zero
 * (64.5 -> "65") where Python rounds them to even ("64"), so ties are handled
 * here. A value is an exact tie at N digits when value * 2^(N+1) is an odd
 * integer; scaling by a power of two is exact.
 */
export function fixed(value, digits = 0) {
  const doubled = value * 2 ** (digits + 1);
  let text;
  if (Number.isInteger(doubled) && Math.abs(doubled % 2) === 1) {
    const scale = 10 ** digits;
    const lower = Math.floor(value * scale); // exact: value * scale is a half-integer
    const even = lower % 2 === 0 ? lower : lower + 1;
    text = (even / scale).toFixed(digits);
  } else {
    text = value.toFixed(digits);
  }
  // Python keeps the sign when a negative value rounds to zero ("-0").
  if (value < 0 && !text.startsWith("-")) text = `-${text}`;
  return text;
}

/** Escape text for insertion into HTML. */
export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ESCAPES[ch]);
}
```

`solar_clock/web/js/theme.js`:

```js
// Colour rules copied from the TFT drawing code so the page matches it.

import { zoned } from "./format.js";

/** Fixed named colours from views/colors.py, e.g. colors.LIGHT_BLUE. */
export function namedColors(data) {
  return data.theme?.colors ?? {};
}

/** CSS custom properties for a palette: background_panel -> --background-panel. */
export function cssVariables(palette) {
  return Object.entries(palette).map(([key, value]) => [`--${key.replaceAll("_", "-")}`, value]);
}

/** Header colour for the time of day (BaseView.get_time_header_color). */
export function timeOfDayHeader(now, sun, colors, timeZone) {
  const times = sun?.times;
  if (times) {
    if (now < new Date(times.dawn)) return colors.DARK_BLUE;
    if (now < new Date(times.sunrise)) return colors.ORANGE;
    if (now < new Date(times.sunset)) return colors.LIGHT_BLUE;
    if (now < new Date(times.dusk)) return colors.ORANGE;
    return colors.PURPLE;
  }
  const { hour } = zoned(now, timeZone);
  if (hour < 6) return colors.DARK_BLUE;
  if (hour < 8) return colors.ORANGE;
  if (hour < 17) return colors.LIGHT_BLUE;
  if (hour < 20) return colors.ORANGE;
  return colors.PURPLE;
}

/** Darkened AQI colour behind the white title (AirQualityView._get_aqi_header_color). */
export function aqiHeaderColor(aqi, colors) {
  if (aqi <= 50) return "#00822d";
  if (aqi <= 100) return "#aa8200";
  if (aqi <= 150) return "#be5500";
  if (aqi <= 200) return "#b91e1e";
  if (aqi <= 300) return colors.AQI_VERY_UNHEALTHY;
  return colors.AQI_HAZARDOUS;
}

/** Colour of the AQI number and category (AirQualityView._get_aqi_text_color). */
export function aqiTextColor(aqi, themeName, colors) {
  if (themeName === "day") return aqiHeaderColor(aqi, colors);
  if (aqi <= 50) return colors.AQI_GOOD;
  if (aqi <= 100) return "#c8b400"; // darker yellow, readable on black
  if (aqi <= 150) return colors.AQI_UNHEALTHY_SENSITIVE;
  if (aqi <= 200) return colors.AQI_UNHEALTHY;
  if (aqi <= 300) return colors.AQI_VERY_UNHEALTHY;
  return colors.AQI_HAZARDOUS;
}

/** Pollutant bar colour by how full the bar is (AirQualityView._render_pollutants). */
export function pollutantBarColor(fraction, colors) {
  if (fraction < 0.5) return colors.AQI_GOOD;
  if (fraction < 0.75) return colors.AQI_MODERATE;
  return colors.AQI_UNHEALTHY;
}
```

`solar_clock/web/js/nav.js`:

```js
// Navigation rules for the page. They never touch the physical clock.

export const SWIPE_MIN_PX = 50;

/** Index after moving `delta` views, wrapping at both ends. */
export function wrapIndex(index, delta, count) {
  return (((index + delta) % count) + count) % count;
}

/** View index named by a URL hash such as "#moon"; 0 (Clock) when unknown. */
export function indexFromHash(hash, names) {
  const index = names.indexOf(hash.replace(/^#/, "").toLowerCase());
  return index === -1 ? 0 : index;
}

/**
 * +1 (next view) for a swipe right, -1 (previous) for a swipe left, else 0.
 * Same direction as the TFT (touch_handler.py: dx > 0 is next).
 */
export function swipeDelta(dx, dy) {
  if (Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) <= Math.abs(dy)) return 0;
  return dx > 0 ? 1 : -1;
}
```

- [ ] **Step 4: Run the tests**

Run: `node --test tests/web/*.test.mjs`
Expected: 18 pass, 0 fail.

`fixed()` was checked against Python's `format()` on 4,016 values, including exact halves and negative zero, with no mismatches. If you change it, re-run that comparison.

- [ ] **Step 5: Add CI.** Apply this change to `.github/workflows/test.yml`:
- The `test` job gets Node, so the Task 6 contract test runs in CI instead of skipping.
- A new `web` job runs the JS tests.
- `actions/setup-node@v7` was released 2026-07-14.

```diff
--- a/.github/workflows/test.yml
+++ b/.github/workflows/test.yml
@@ -35,6 +35,11 @@
           pip install -r requirements.txt
           pip install -r requirements-dev.txt

+      - name: Set up Node.js (web page contract test)
+        uses: actions/setup-node@v7
+        with:
+          node-version: '22'
+
       - name: Run tests with coverage
         run: |
           pytest tests/ -v --cov=solar_clock --cov-report=xml --cov-report=term-missing
@@ -45,6 +50,19 @@
         with:
           files: ./coverage.xml
           fail_ci_if_error: false
+
+  web:
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v6
+
+      - name: Set up Node.js
+        uses: actions/setup-node@v7
+        with:
+          node-version: '22'
+
+      - name: Run web page tests
+        run: node --test tests/web/*.test.mjs

   lint:
     runs-on: ubuntu-latest
```

Check the YAML still parses: `./venv/bin/python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/test.yml'))" 2>/dev/null || python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"`. The pre-commit `check-yaml` hook also checks it at commit.

- [ ] **Step 6: Commit**

```bash
git add solar_clock/web/package.json solar_clock/web/js/format.js solar_clock/web/js/theme.js solar_clock/web/js/nav.js tests/web/ .github/workflows/test.yml
git commit -m "Add the web page's formatting, colour and navigation helpers" -m "Pure ES modules that copy the TFT's strftime patterns and colour rules, tested with node --test; CI gains a web job." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Page shell and the Clock view

**Files:**
- Create: `solar_clock/web/index.html`, `solar_clock/web/style.css`, `solar_clock/web/js/app.js`, `solar_clock/web/js/views/index.js`, `solar_clock/web/js/views/clock.js`
- Create: `tests/web/dom-stub.mjs`, `tests/web/app.test.mjs`, `tests/web/views.test.mjs`, `tests/web/clock.test.mjs`
- Create: `tests/test_web_page_files.py`, `tests/test_web_contract.py`

**Interfaces:**
- Consumes: everything from Task 5; `StaticSite` and `WEB_DIR` (Task 3); `WebDataService` (Task 2).
- Produces:
  - **View contract.** Every module in `js/views/` exports `name` (a URL hash token), `title` (string) and `render(data, now) -> string`. `data` is an `/api/now` object; `now` is a `Date`.
    - `render` must cope with any data section being `null`.
    - It must escape API text with `escapeHtml`.
    - It returns markup for the `<main id="view">` element.
  - **`VIEWS`** (in `js/views/index.js`) lists the views in TFT order.
  - **Page elements** `app.js` uses: `#banner`, `#view`, `#dots`, `#prev` and `#next`.
  - **Shared CSS classes:**
    - `view-header`, `view-body`, `row`, `panel` (plus `dark` and `boxed`), `label`, `value`, `small` and `message`;
    - colour tones `primary`, `secondary`, `sun`, `warm`, `cool` and `moon`;
    - `footer`, `stat` and `block`.

- [ ] **Step 1: Write the failing tests**

`tests/web/dom-stub.mjs` is just enough of a browser to run `app.js` in Node:

```js
// Just enough of a browser for app.js: the five page elements, events, the
// root style, location/history and fetch. setInterval is recorded, not run.

function eventTarget(extra = {}) {
  const handlers = {};
  return Object.assign(
    {
      addEventListener(type, fn) {
        (handlers[type] ??= []).push(fn);
      },
      dispatch(type, event = {}) {
        for (const fn of handlers[type] ?? []) fn(event);
      },
    },
    extra,
  );
}

const GLOBALS = ["document", "window", "location", "history", "fetch", "setInterval"];

/**
 * Install a fake page. `responses` are served to fetch() in order: an object
 * is a 200 JSON body, an Error is a network failure, null never answers.
 */
export function installDom({ hash = "", responses = [] } = {}) {
  const saved = Object.fromEntries(GLOBALS.map((name) => [name, globalThis[name]]));
  const elements = {};
  for (const id of ["banner", "view", "dots", "prev", "next"]) {
    elements[id] = eventTarget({
      innerHTML: "",
      textContent: "",
      hidden: false,
      attributes: {},
      setAttribute(name, value) {
        this.attributes[name] = value;
      },
    });
  }
  const rootStyle = {
    props: {},
    colorScheme: "",
    setProperty(name, value) {
      this.props[name] = value;
    },
  };
  const location = { hash };
  const fetchCalls = [];
  Object.assign(globalThis, {
    document: eventTarget({
      visibilityState: "visible",
      documentElement: { style: rootStyle },
      getElementById: (id) => elements[id],
    }),
    window: eventTarget(),
    location,
    history: {
      replaceState(_state, _title, url) {
        location.hash = url;
      },
    },
    fetch(url, options) {
      fetchCalls.push({ url, options });
      const next = responses.shift();
      if (next === null || next === undefined) return new Promise(() => {});
      if (next instanceof Error) return Promise.reject(next);
      return Promise.resolve({ ok: true, status: 200, json: async () => next });
    },
    setInterval: () => 0,
  });
  return {
    elements,
    rootStyle,
    location,
    fetchCalls,
    responses,
    restore() {
      Object.assign(globalThis, saved);
    },
  };
}

/** Let pending promises (the fetch and its .json()) settle. */
export async function settle() {
  for (let i = 0; i < 5; i += 1) await new Promise((resolve) => setImmediate(resolve));
}

let loads = 0;

/** Run app.js against the installed page; each call gets a fresh copy. */
export async function loadApp() {
  loads += 1;
  await import(`../../solar_clock/web/js/app.js?load=${loads}`);
  await settle();
}
```

`tests/web/app.test.mjs` is written against the view list, so it keeps passing as Tasks 7–8 add views:

```js
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";

import { VIEWS } from "../../solar_clock/web/js/views/index.js";
import { installDom, loadApp, settle } from "./dom-stub.mjs";
import { sampleNow } from "./fixtures.mjs";

// Written against the view list, so it holds as views are added.
const names = VIEWS.map((v) => v.name);
const nameAt = (i) => names[((i % names.length) + names.length) % names.length];

let page;
afterEach(() => page.restore());

function dayData() {
  const data = sampleNow();
  data.theme.active = "day";
  return data;
}

test("before the first answer the page says it is connecting", async () => {
  page = installDom({ responses: [null] });
  await loadApp();
  assert.equal(page.elements.banner.hidden, false);
  assert.equal(page.elements.banner.textContent, "Connecting to clock…");
  assert.equal(page.elements.view.innerHTML, "");
});

test("the first answer draws the Clock view in the clock's theme", async () => {
  page = installDom({ responses: [sampleNow()] });
  await loadApp();
  assert.equal(page.fetchCalls[0].url, "/api/now");
  assert.equal(page.fetchCalls[0].options.cache, "no-store");
  assert.equal(page.elements.banner.hidden, true);
  assert.match(page.elements.view.innerHTML, /Sunrise/);
  assert.equal(page.rootStyle.props["--background"], "#000000");
  assert.equal(page.rootStyle.colorScheme, "dark");
});

test("losing the clock keeps the last data and says so, then recovers", async () => {
  page = installDom({ responses: [sampleNow(), new Error("offline")] });
  await loadApp();
  document.dispatch("visibilitychange"); // waking the page polls at once
  await settle();
  assert.equal(page.fetchCalls.length, 2);
  assert.equal(page.elements.banner.hidden, false);
  assert.match(page.elements.banner.textContent, /^Can't reach clock · last update \d{1,2}:\d\d [AP]M$/);
  assert.match(page.elements.view.innerHTML, /Sunrise/);

  page.responses.push(sampleNow());
  document.dispatch("visibilitychange");
  await settle();
  assert.equal(page.elements.banner.hidden, true);
});

test("a theme change on the clock reaches an open page", async () => {
  page = installDom({ responses: [sampleNow(), dayData()] });
  await loadApp();
  document.dispatch("visibilitychange");
  await settle();
  assert.equal(page.rootStyle.props["--background"], "#f5f3eb");
  assert.equal(page.rootStyle.colorScheme, "light");
});

test("a link to a view opens it; buttons and arrow keys move and wrap", async () => {
  const last = names.length - 1;
  page = installDom({ hash: `#${nameAt(last)}`, responses: [sampleNow()] });
  await loadApp();
  assert.equal(page.elements.dots.attributes["aria-label"], `${VIEWS[last].title}, view ${last + 1} of ${names.length}`);

  page.elements.next.dispatch("click");
  assert.equal(page.location.hash, `#${nameAt(0)}`);
  assert.match(page.elements.view.innerHTML, /Sunrise/);

  document.dispatch("keydown", { key: "ArrowLeft" });
  assert.equal(page.location.hash, `#${nameAt(last)}`);
  page.elements.prev.dispatch("click");
  assert.equal(page.location.hash, `#${nameAt(last - 1)}`);
});

test("an unknown link opens Clock", async () => {
  page = installDom({ hash: "#nowhere", responses: [sampleNow()] });
  await loadApp();
  assert.match(page.elements.view.innerHTML, /Sunrise/);
});

test("a swipe right moves to the next view, as on the TFT; a vertical drag does not", async () => {
  page = installDom({ responses: [sampleNow()] });
  await loadApp();
  const swipe = (from, to) => {
    page.elements.view.dispatch("touchstart", { changedTouches: [from] });
    page.elements.view.dispatch("touchend", { changedTouches: [to] });
  };
  swipe({ clientX: 200, clientY: 100 }, { clientX: 190, clientY: 400 });
  assert.equal(page.location.hash, "");
  swipe({ clientX: 120, clientY: 200 }, { clientX: 300, clientY: 210 });
  assert.equal(page.location.hash, `#${nameAt(1)}`);
});

test("a view that throws shows a message instead of a blank page", async () => {
  const broken = sampleNow();
  broken.location = null; // every view reads location
  page = installDom({ responses: [broken] });
  await loadApp();
  assert.equal(page.elements.view.innerHTML, `<p class="message">Couldn't draw this view</p>`);
  page.elements.next.dispatch("click");
  assert.equal(page.location.hash, `#${nameAt(1)}`);
});
```

`tests/web/views.test.mjs`. At this stage only Clock exists; Tasks 7 and 8 extend the list on the first assertion line.

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { VIEWS } from "../../solar_clock/web/js/views/index.js";
import { HOSTILE, NOW, sampleNow } from "./fixtures.mjs";

test("views come in TFT order and each has a name, title and render()", () => {
  assert.deepEqual(VIEWS.map((v) => v.name), ["clock"]);
  for (const view of VIEWS) {
    assert.equal(typeof view.title, "string");
    assert.equal(typeof view.render(sampleNow(), NOW), "string");
  }
});

test("every view renders when every data section is null", () => {
  const empty = sampleNow();
  for (const key of ["theme", "sun", "weather", "air_quality", "moon"]) empty[key] = null;
  for (const view of VIEWS) assert.equal(typeof view.render(empty, NOW), "string", view.name);
});

test("text from the API is escaped in every view", () => {
  const data = sampleNow();
  data.location.name = HOSTILE;
  data.weather.current.description = HOSTILE;
  data.weather.current.wind_direction = HOSTILE;
  data.air_quality.category = HOSTILE;
  data.sun.next_event.name = HOSTILE;
  data.moon.phase.phase_name = HOSTILE;
  for (const view of VIEWS) {
    assert.ok(!view.render(data, NOW).includes("<img"), `${view.name} let markup through`);
  }
});
```

`tests/web/clock.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { render } from "../../solar_clock/web/js/views/clock.js";
import { NOW, assertShows, sampleNow } from "./fixtures.mjs";

test("clock view matches the TFT's text", () => {
  assertShows(render(sampleNow(), NOW), [
    "3:12:00", "PM", "Thursday, October 08, 2026", "7:08 AM", "11h 30m", "6:35 PM",
    "Scattered Clouds", "Temp: 64°F", "Humidity: 58%", "El: 31° ↑", "Az: 223° SW",
    "63% of day", "Sunset in 3h 23m", "background:#87ceeb",
  ]);
});

test("without weather it says so and hides sun position, like the TFT", () => {
  const data = sampleNow();
  data.weather = null;
  const html = render(data, NOW);
  assertShows(html, ["Weather: unavailable", "7:08 AM"]);
  assert.ok(!html.includes("Sun Position"));
});

test("without sun data it still shows the time and date", () => {
  const data = sampleNow();
  data.sun = null;
  const html = render(data, NOW);
  assertShows(html, ["3:12:00", "Thursday, October 08, 2026"]);
  assert.ok(!html.includes("Sunrise"));
  assert.ok(!html.includes(" in "));
});
```

`tests/test_web_page_files.py` checks that `index.html` and every JS import point at files the server actually serves:

```python
"""Checks on the web page's own files in solar_clock/web/."""

import re
from html.parser import HTMLParser
from pathlib import PurePosixPath

from solar_clock.web_static import WEB_DIR, StaticSite

# Relative module imports in the page's JavaScript, e.g. from "./format.js".
JS_IMPORT = re.compile(
    r"""^\s*(?:import|export)\b[^;]*?\bfrom\s+["'](\.[^"']+)["']""", re.MULTILINE
)


class _References(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.refs.append(value)


def _index_references() -> list[str]:
    parser = _References()
    parser.feed((WEB_DIR / "index.html").read_text())
    return parser.refs


def test_every_index_reference_is_served():
    site = StaticSite()
    refs = _index_references()
    assert "/js/app.js" in refs
    for ref in refs:
        assert ref.startswith("/"), f"{ref} should be an absolute path"
        assert site.resolve(ref) is not None, f"index.html points at missing {ref}"


def test_every_javascript_import_is_served():
    site = StaticSite()
    scripts = sorted(WEB_DIR.glob("js/**/*.js"))
    assert scripts, "no JavaScript found"
    for script in scripts:
        url_dir = PurePosixPath("/" + script.parent.relative_to(WEB_DIR).as_posix())
        for target in JS_IMPORT.findall(script.read_text()):
            parts: list[str] = []
            for part in (url_dir / target).parts[1:]:
                if part == "..":
                    parts.pop()
                elif part != ".":
                    parts.append(part)
            url = "/" + "/".join(parts)
            assert site.resolve(url) is not None, f"{script.name} imports missing {url}"
```

`tests/test_web_contract.py` is Review Focus item 1. It feeds the real `/api/now` JSON through Node into every view:

```python
"""The real /api/now JSON must render in every view of the page.

The JavaScript tests use a hand-written sample; this test feeds the page's
views the JSON that WebDataService actually builds, through Node.js, so a
renamed or missing field fails here instead of on a phone. Skipped when Node
is not installed.
"""

import json
import shutil
import subprocess
from unittest.mock import MagicMock

import pytest

from solar_clock.data.weather import AirQuality, CurrentWeather, DailyForecast
from solar_clock.web_api import WebDataService
from solar_clock.web_static import WEB_DIR

NODE = shutil.which("node")

RENDER_EVERY_VIEW = """
let text = "";
for await (const chunk of process.stdin) text += chunk;
const data = JSON.parse(text);
const { VIEWS } = await import(process.argv[1]);
const out = {};
for (const view of VIEWS) out[view.name] = view.render(data, new Date(data.generated_at));
process.stdout.write(JSON.stringify(out));
"""


def _weather():
    provider = MagicMock()
    provider.get_current_weather.return_value = CurrentWeather(
        temperature=64.5,
        feels_like=63.2,
        humidity=58,
        description="Scattered Clouds",
        wind_speed=7.4,
        wind_direction="WSW",
    )
    provider.get_forecast.return_value = [
        DailyForecast(date="2026-10-08", high_temp=66.1, low_temp=51.3, rain_chance=10),
        DailyForecast(date="2026-10-09", high_temp=61.0, low_temp=48.8, rain_chance=40),
        DailyForecast(date="2026-10-10", high_temp=58.4, low_temp=45.0, rain_chance=0),
    ]
    provider.get_air_quality.return_value = AirQuality(
        aqi=42,
        category="Good",
        pm25=10.1,
        pm10=18.4,
        o3=61.2,
        no2=12.7,
        so2=1.9,
        co=230.5,
        updated_at=1791485880.0,
    )
    return provider


@pytest.mark.skipif(NODE is None, reason="Node.js is not installed")
@pytest.mark.parametrize("weather", [_weather, lambda: None], ids=["weather", "no-key"])
def test_every_view_renders_the_real_api_response(sample_config, weather):
    service = WebDataService(
        sample_config, weather=weather(), theme_mode=lambda: "auto"
    )
    payload = json.dumps(service.build_now())
    views_module = (WEB_DIR / "js" / "views" / "index.js").as_uri()
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", RENDER_EVERY_VIEW, views_module],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    rendered = json.loads(result.stdout)
    assert rendered, "no views rendered"
    for name, html in rendered.items():
        assert html.strip(), f"{name} rendered nothing"
        for broken in ("undefined", "NaN", "Invalid Date"):
            assert broken not in html, f"{name} shows {broken!r}"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `node --test tests/web/*.test.mjs` and `./venv/bin/pytest tests/test_web_page_files.py tests/test_web_contract.py -v`
Expected: the JS run fails with `ERR_MODULE_NOT_FOUND` for `views/index.js`, `views/clock.js` and `app.js`. The Python tests fail with `FileNotFoundError: Web page missing: …/solar_clock/web/index.html`, or a missing `views/index.js`.

- [ ] **Step 3: Implement.** `solar_clock/web/index.html`. The banner starts visible, so the page reads "Connecting to clock…" before any script runs.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Solar Clock</title>
<meta name="apple-mobile-web-app-title" content="Solar Clock">
<link rel="icon" href="/icons/icon.svg" type="image/svg+xml">
<link rel="icon" href="/icons/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="stylesheet" href="/style.css">
<script type="module" src="/js/app.js"></script>
</head>
<body>
<div id="banner" class="banner" role="status">Connecting to clock…</div>
<main id="view" class="view"></main>
<nav class="navbar" aria-label="Views">
  <button id="prev" class="nav-btn" type="button" aria-label="Previous view">&lt;</button>
  <div id="dots" class="dots"></div>
  <button id="next" class="nav-btn" type="button" aria-label="Next view">&gt;</button>
</nav>
</body>
</html>
```

`solar_clock/web/style.css`:
- The defaults are the night theme, so the first paint matches the clock at night.
- `app.js` overwrites the colour variables from `/api/now`.
- It includes the CSS for all five phase 1 views, so Tasks 7–8 add no CSS.

```css
/* Solar Clock web page. app.js sets the colour variables from the clock's
   theme (/api/now); the values below are the night theme, used until the
   first response arrives. */
:root {
  --background: #000000;
  --background-panel: #232328;
  --background-panel-dark: #191e19;
  --text-primary: #ffffff;
  --text-secondary: #b4b4b4;
  --text-tertiary: #808080;
  --nav-background: #000000;
  --nav-button: #3c3c3c;
  --nav-dot-active: #ffffff;
  --nav-dot-inactive: #808080;
  --clock-face: #f0f0e6;
  --clock-hands: #000000;
  --clock-markers: #323232;
  --divider: #282832;
  --outline: #808080;
  --accent-sun: #ffdc32;
  --accent-warm: #ff961e;
  --accent-moon: #fff8dc;
  --accent-cool: #6495ed;
  --accent-green: #00c800;
  color-scheme: dark;
}

* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  display: flex;
  flex-direction: column;
  background: var(--background);
  color: var(--text-primary);
  font-family: "DejaVu Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 16px;
  line-height: 1.35;
  -webkit-text-size-adjust: 100%;
}
[hidden] { display: none !important; }

.banner {
  padding: calc(6px + env(safe-area-inset-top, 0px)) 16px 6px;
  background: var(--accent-warm);
  color: #000000;
  font-size: 14px;
  text-align: center;
}
.view { flex: 1; width: 100%; max-width: 760px; margin: 0 auto; touch-action: pan-y; }
.view-header {
  display: flex; align-items: baseline; justify-content: center; gap: 6px;
  padding: 8px 16px; color: #ffffff;
}
.view-header h2 { margin: 0; font-size: 24px; font-weight: 700; }
.view-body { display: grid; gap: 14px; padding: 12px 16px 20px; }
.view-body p { margin: 0; }

.row { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.panel { min-width: 0; padding: 10px 12px; border-radius: 8px; background: var(--background-panel); }
.panel.dark { background: var(--background-panel-dark); }
.panel.boxed { border: 1px solid var(--outline); border-radius: 0; }
.panel > span, .stat > span, .sun-row span, .block { display: block; }
.panel-title { margin: 0 0 4px; font-size: 16px; }

.label { color: var(--text-tertiary); font-size: 14px; }
.value { font-size: 20px; font-weight: 700; }
.small { font-size: 13px; }
.primary { color: var(--text-primary); }
.secondary { color: var(--text-secondary); }
.sun { color: var(--accent-sun); }
.warm { color: var(--accent-warm); }
.cool { color: var(--accent-cool); }
.moon { color: var(--accent-moon); }
.message { padding: 48px 16px; color: var(--text-secondary); font-size: 18px; text-align: center; }
.footer { display: flex; justify-content: space-between; gap: 12px; color: var(--text-tertiary); font-size: 14px; }

.navbar {
  position: sticky; bottom: 0;
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 6px 10px calc(6px + env(safe-area-inset-bottom, 0px));
  background: var(--nav-background);
}
.nav-btn {
  width: 50px; height: 34px;
  border: 1px solid #808080; background: var(--nav-button); color: #ffffff;
  font: inherit; font-size: 20px; cursor: pointer;
}
.nav-btn:focus-visible { outline: 2px solid var(--accent-sun); outline-offset: 2px; }
.dots { display: flex; gap: 6px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--nav-dot-inactive); }
.dot.active { background: var(--nav-dot-active); }

/* Clock */
.clock-header { padding-block: 2px 4px; }
.clock-time { color: var(--text-primary); font-size: 46px; font-weight: 700; font-variant-numeric: tabular-nums; }
.clock-ampm { color: var(--text-secondary); font-size: 24px; }
.clock-date { font-size: 18px; text-align: center; }
.sun-row { display: grid; grid-template-columns: 1fr auto 1fr; gap: 8px; }
.sun-row .center { text-align: center; }
.sun-row .right { text-align: right; }
.progress { display: grid; justify-items: center; gap: 4px; font-size: 14px; }
.bar { width: min(100%, 260px); height: 12px; border: 1px solid var(--text-secondary); background: var(--text-tertiary); }
.bar-fill { height: 100%; background: var(--accent-sun); }

/* Weather */
.temp-big { font-size: 48px; font-weight: 700; line-height: 1.1; }
.description { margin-top: 6px; }
.forecast { width: 100%; border-collapse: collapse; }
.forecast th {
  padding: 2px 4px 6px; border-bottom: 1px solid var(--divider);
  color: var(--text-tertiary); font-size: 12px; font-weight: 400; text-align: left;
}
.forecast td { padding: 10px 4px; border-bottom: 1px solid var(--divider); }
.forecast tr:last-child td { border-bottom: none; }
.forecast .num { font-size: 18px; font-weight: 700; }

/* Air quality */
.aqi-value { font-size: 56px; font-weight: 700; line-height: 1.05; }
.aqi-category { font-size: 20px; font-weight: 700; }
.pollutant { display: grid; grid-template-columns: 48px 1fr 56px; align-items: center; gap: 8px; margin-top: 8px; }
.pollutant-name { color: var(--text-secondary); font-size: 14px; text-align: right; }
.pollutant-bar { height: 16px; overflow: hidden; border-radius: 3px; background: var(--divider); }
.pollutant-fill { display: block; height: 100%; border-radius: 3px; }
.pollutant-value { font-size: 12px; }

/* Solar details */
.times-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.times-grid .stat + .stat { margin-top: 8px; }
.golden h3 { margin: 0 0 6px; color: var(--accent-warm); font-size: 16px; }
.golden-row .label { display: inline; }

/* Moon */
.moon-top { display: flex; align-items: center; gap: 20px; }
.moon-disc { width: 110px; height: 110px; flex: none; }
.moon-illum { display: block; font-size: 36px; font-weight: 700; }
.cycle { position: relative; display: block; height: 10px; margin-top: 8px; background: var(--divider); }
.cycle-fill { position: absolute; top: 0; bottom: 0; left: 0; }
.cycle-full { position: absolute; top: -2px; bottom: -2px; left: 50%; width: 2px; background: var(--accent-moon); }
```

`solar_clock/web/js/app.js`:

```js
// Page shell: polls /api/now, redraws the current view every second, and
// handles navigation. It only reads from the clock; it never changes it.

import { time12 } from "./format.js";
import { indexFromHash, swipeDelta, wrapIndex } from "./nav.js";
import { cssVariables } from "./theme.js";
import { VIEWS } from "./views/index.js";

const POLL_MS = 60_000;
const TICK_MS = 1_000;

const els = {
  banner: document.getElementById("banner"),
  view: document.getElementById("view"),
  dots: document.getElementById("dots"),
  prev: document.getElementById("prev"),
  next: document.getElementById("next"),
};

const state = {
  data: null,
  lastOk: null,
  failing: false,
  theme: null,
  index: indexFromHash(location.hash, VIEWS.map((v) => v.name)),
};

function applyTheme(theme) {
  if (!theme || theme.active === state.theme) return;
  for (const [name, value] of cssVariables(theme.palettes[theme.active])) {
    document.documentElement.style.setProperty(name, value);
  }
  document.documentElement.style.colorScheme = theme.active === "day" ? "light" : "dark";
  state.theme = theme.active;
}

function renderBanner() {
  if (state.data === null) {
    els.banner.textContent = "Connecting to clock…";
    els.banner.hidden = false;
  } else if (state.failing) {
    const last = time12(state.lastOk, state.data.location.timezone);
    els.banner.textContent = `Can't reach clock · last update ${last}`;
    els.banner.hidden = false;
  } else {
    els.banner.hidden = true;
  }
}

function renderDots() {
  els.dots.innerHTML = VIEWS.map(
    (v, i) => `<span class="dot${i === state.index ? " active" : ""}"></span>`,
  ).join("");
  els.dots.setAttribute("aria-label", `${VIEWS[state.index].title}, view ${state.index + 1} of ${VIEWS.length}`);
}

function render() {
  renderBanner();
  renderDots();
  if (state.data === null) return;
  const view = VIEWS[state.index];
  try {
    els.view.innerHTML = view.render(state.data, new Date());
  } catch (err) {
    console.error(`The ${view.name} view failed to draw`, err);
    els.view.innerHTML = `<p class="message">Couldn't draw this view</p>`;
  }
}

async function poll() {
  try {
    const response = await fetch("/api/now", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    state.lastOk = new Date();
    state.failing = false;
    applyTheme(state.data.theme);
  } catch (err) {
    console.warn("Could not reach the clock", err);
    state.failing = true;
  }
  render();
}

function go(delta) {
  state.index = wrapIndex(state.index, delta, VIEWS.length);
  history.replaceState(null, "", `#${VIEWS[state.index].name}`);
  render();
}

els.prev.addEventListener("click", () => go(-1));
els.next.addEventListener("click", () => go(1));
document.addEventListener("keydown", (e) => {
  if (e.key === "ArrowLeft") go(-1);
  if (e.key === "ArrowRight") go(1);
});
window.addEventListener("hashchange", () => {
  state.index = indexFromHash(location.hash, VIEWS.map((v) => v.name));
  render();
});

let touchStart = null;
els.view.addEventListener("touchstart", (e) => {
  const t = e.changedTouches[0];
  touchStart = { x: t.clientX, y: t.clientY };
}, { passive: true });
els.view.addEventListener("touchend", (e) => {
  if (touchStart === null) return;
  const t = e.changedTouches[0];
  const delta = swipeDelta(t.clientX - touchStart.x, t.clientY - touchStart.y);
  touchStart = null;
  if (delta !== 0) go(delta);
}, { passive: true });

// A phone reopening the page from the home screen gets fresh data at once.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") poll();
});

render();
poll();
setInterval(poll, POLL_MS);
setInterval(render, TICK_MS);
```

`solar_clock/web/js/views/index.js` (Clock only for now):

```js
// Views in the same order as the TFT (solar_clock/views/__init__.py).

import * as clock from "./clock.js";

export const VIEWS = [clock];
```

`solar_clock/web/js/views/clock.js`:

```js
// Clock view: mirrors solar_clock/views/clock.py.

import {
  clockParts, compass8, countdownHM, dayFraction, dayLengthPadded, escapeHtml, fixed,
  longDate, time12,
} from "../format.js";
import { namedColors, timeOfDayHeader } from "../theme.js";

export const name = "clock";
export const title = "Clock";

export function render(data, now) {
  const tz = data.location.timezone;
  const { time, ampm } = clockParts(now, tz);
  const header = timeOfDayHeader(now, data.sun, namedColors(data), tz);
  return `<header class="view-header clock-header" style="background:${header}">
  <span class="clock-time">${time}</span><span class="clock-ampm">${ampm}</span>
</header>
<div class="view-body">
  <p class="clock-date">${longDate(now, tz)}</p>
  ${sunRow(data.sun, tz)}
  ${weatherRow(data)}
  ${progress(data.sun, now, tz)}
</div>`;
}

function sunRow(sun, tz) {
  if (!sun) return "";
  const daylight = sun.day_length_hours
    ? `<span class="label">daylight</span><span class="value">${dayLengthPadded(sun.day_length_hours)}</span>`
    : "";
  return `<div class="sun-row">
    <div><span class="label">Sunrise</span><span class="value sun">${time12(sun.times.sunrise, tz)}</span></div>
    <div class="center">${daylight}</div>
    <div class="right"><span class="label">Sunset</span><span class="value warm">${time12(sun.times.sunset, tz)}</span></div>
  </div>`;
}

// As on the TFT, sun position is only shown alongside the weather.
function weatherRow(data) {
  const current = data.weather?.current;
  if (!current) return `<p class="secondary">Weather: unavailable</p>`;
  const unit = data.units === "metric" ? "°C" : "°F";
  return `<div class="row">
    <section class="panel">
      <span class="value">${escapeHtml(current.description)}</span>
      <span class="sun">Temp: ${fixed(current.temperature)}${unit}</span>
      <span class="secondary">Humidity: ${current.humidity}%</span>
    </section>
    ${sunPosition(data.sun?.position)}
  </div>`;
}

function sunPosition(position) {
  if (!position) return "";
  const arrow = position.elevation >= 0 ? "↑" : "↓";
  const tone = position.elevation > 0 ? "sun" : "warm";
  return `<section class="panel">
      <span class="label">Sun Position</span>
      <span class="${tone}">El: ${fixed(Math.abs(position.elevation))}° ${arrow}</span>
      <span class="secondary">Az: ${fixed(position.azimuth)}° ${compass8(position.azimuth)}</span>
    </section>`;
}

function progress(sun, now, tz) {
  const fraction = dayFraction(now, tz);
  const next = sun?.next_event;
  const left = next ? countdownHM(next.at, now) : null;
  const countdown = left ? `<p>${escapeHtml(next.name)} in ${left.h}h ${left.m}m</p>` : "";
  return `<div class="progress">
    <div class="bar"><div class="bar-fill" style="width:${(fraction * 100).toFixed(2)}%"></div></div>
    <p class="secondary">${fixed(fraction * 100)}% of day</p>
    ${countdown}
  </div>`;
}
```

- [ ] **Step 4: Run the tests**

Run: `node --test tests/web/*.test.mjs`, then `./venv/bin/pytest`
Expected: JS 32 pass, 0 fail. Python: the full suite passes with 303 passed and 3 skipped. The contract test runs 2 cases and needs `node` on PATH; it skips otherwise.

- [ ] **Step 5: Look at it.** Start the preview as in Task 4 Step 5, but with `--bind 0.0.0.0`.
- `curl -s http://127.0.0.1:8091/ | head -3` should show the page.
- If Peter is around, he can open `http://<homelab>:8091/` on his phone now. Otherwise the full look is checked in Task 10.
- Stop the server by PID.

- [ ] **Step 6: Extra gates, lint, commit**

```bash
<scratchpad>/ruffenv/bin/ruff check --no-cache --target-version py39 tests/test_web_page_files.py tests/test_web_contract.py
./venv/bin/black --check solar_clock tests && ./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503 && ./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
git add solar_clock/web/index.html solar_clock/web/style.css solar_clock/web/js/app.js solar_clock/web/js/views/ tests/web/ tests/test_web_page_files.py tests/test_web_contract.py
git commit -m "Add the web page shell and its Clock view" -m "Polls /api/now every 60 s and on wake, redraws each second, follows the clock's theme, swipes/keys/buttons between views, and says when the clock can't be reached." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Weather and Air Quality views

**Files:**
- Create: `solar_clock/web/js/views/weather.js`, `solar_clock/web/js/views/airquality.js`, `tests/web/weather.test.mjs`, `tests/web/airquality.test.mjs`
- Modify: `solar_clock/web/js/views/index.js`, `tests/web/views.test.mjs` (the order assertion)

**Interfaces:**
- Consumes: the view contract and CSS classes (Task 6); `format.js` and `theme.js` (Task 5).
- Produces: views `weather` ("Weather") and `airquality` ("Air Quality"), registered after `clock`.

TFT behaviours these views copy (from `solar_clock/views/weather.py` and `airquality.py`):
- **Weather:**
  - The forecast labels are "Today", "Tmrw", then the short weekday name.
  - Rain of 30% or more shows in the cool accent.
  - With no current weather, the view shows "Weather data unavailable".
- **Air Quality:**
  - The header uses the darkened AQI colours.
  - In the night theme, the number uses the bright AQI colours, with Moderate as `#c8b400`; in the day theme it uses the darkened ones.
  - Each pollutant bar fills relative to a fixed full-scale value: PM2.5 50, PM10 100, O3 100, NO2 50, CO 5000.
  - A bar is green below half full, yellow below three-quarters, red above. A fill of 3 px or less (of 120 px) is not drawn.
  - With no data, the view shows "No data available" with no header.

- [ ] **Step 1: Write the failing tests**

`tests/web/weather.test.mjs`:

```js
import { test } from "node:test";

import { render } from "../../solar_clock/web/js/views/weather.js";
import { NOW, assertShows, sampleNow } from "./fixtures.mjs";

test("weather view matches the TFT's text", () => {
  assertShows(render(sampleNow(), NOW), [
    "Weather", "64°F", "Feels 63°", "Humidity 58%", "Wind 7 WSW", "Scattered Clouds",
    "Today", "Tmrw", "Sat", "66°", "51°", '<td class="secondary">10%</td>',
    '<td class="cool">40%</td>', "Test City",
  ]);
});

test("without weather it shows the TFT message", () => {
  const data = sampleNow();
  data.weather = null;
  assertShows(render(data, NOW), ["Weather data unavailable", "Test City"]);
});
```

`tests/web/airquality.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { render } from "../../solar_clock/web/js/views/airquality.js";
import { NOW, assertShows, sampleNow } from "./fixtures.mjs";

test("air quality view matches the TFT's text and colours", () => {
  assertShows(render(sampleNow(), NOW), [
    "background:#00822d", "US EPA AQI", ">42<", "Good", "PM2.5", "10.1", "61.2",
    "230.5", "background:#ffff00", "Updated 2:58 PM", "Test City",
  ]);
});

test("a pollutant bar too small for the TFT to draw is left empty", () => {
  const data = sampleNow();
  data.air_quality.co = 100; // 2% of 5000: int(120 * 0.02) = 2 px, not drawn
  const html = render(data, NOW);
  const coRow = html.slice(html.indexOf(">CO<"));
  assert.ok(!coRow.slice(0, coRow.indexOf("</div>")).includes("pollutant-fill"));
});

test("without data there is no header, like the TFT", () => {
  const data = sampleNow();
  data.air_quality = null;
  const html = render(data, NOW);
  assertShows(html, ["No data available"]);
  assert.ok(!html.includes("<header"));
});
```

In `tests/web/views.test.mjs`, change the order assertion to:

```js
  assert.deepEqual(VIEWS.map((v) => v.name), ["clock", "weather", "airquality"]);
```

- [ ] **Step 2: Run them and watch them fail**

Run: `node --test tests/web/*.test.mjs`
Expected: `weather.test.mjs` and `airquality.test.mjs` fail with `ERR_MODULE_NOT_FOUND`. In `views.test.mjs`, the first test fails because the list is still `["clock"]`.

- [ ] **Step 3: Implement.** `solar_clock/web/js/views/weather.js`:

```js
// Weather view: mirrors solar_clock/views/weather.py.

import { escapeHtml, fixed, weekdayShort } from "../format.js";
import { namedColors } from "../theme.js";

export const name = "weather";
export const title = "Weather";

const NEAR_DAYS = ["Today", "Tmrw"];

export function render(data) {
  const colors = namedColors(data);
  const header = `<header class="view-header" style="background:${colors.LIGHT_BLUE}"><h2>Weather</h2></header>`;
  const footer = `<p class="footer"><span>${escapeHtml(data.location.name)}</span></p>`;
  const current = data.weather?.current;
  if (!current) {
    return `${header}<div class="view-body"><p class="message">Weather data unavailable</p>${footer}</div>`;
  }
  const unit = data.units === "metric" ? "°C" : "°F";
  return `${header}
<div class="view-body">
  <div class="row">
    <section class="panel">
      <span class="temp-big">${fixed(current.temperature)}${unit}</span>
      <span class="secondary small">Feels ${fixed(current.feels_like)}°</span>
      <span class="secondary small">Humidity ${current.humidity}%</span>
      <span class="secondary small">Wind ${fixed(current.wind_speed)} ${escapeHtml(current.wind_direction)}</span>
      <span class="sun description">${escapeHtml(current.description)}</span>
    </section>
    <section class="panel">${forecastTable(data.weather.forecast)}</section>
  </div>
  ${footer}
</div>`;
}

function forecastTable(days) {
  const rows = days
    .slice(0, 3)
    .map((day, i) => {
      const label = i < NEAR_DAYS.length ? NEAR_DAYS[i] : weekdayShort(day.date);
      const rain = day.rain_chance < 30 ? "secondary" : "cool";
      return `<tr><td>${label}</td><td class="num warm">${fixed(day.high_temp)}°</td><td class="num cool">${fixed(day.low_temp)}°</td><td class="${rain}">${day.rain_chance}%</td></tr>`;
    })
    .join("");
  return `<table class="forecast">
      <thead><tr><th>Day</th><th>Hi</th><th>Lo</th><th>Rain</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
```

`solar_clock/web/js/views/airquality.js`:

```js
// Air Quality view: mirrors solar_clock/views/airquality.py.

import { escapeHtml, fixed, time12 } from "../format.js";
import { aqiHeaderColor, aqiTextColor, namedColors, pollutantBarColor } from "../theme.js";

export const name = "airquality";
export const title = "Air Quality";

// [label, field, value that fills the bar]
const POLLUTANTS = [
  ["PM2.5", "pm25", 50],
  ["PM10", "pm10", 100],
  ["O3", "o3", 100],
  ["NO2", "no2", 50],
  ["CO", "co", 5000],
];
// The TFT's bars are 120 px wide and it skips fills of 3 px or less.
const TFT_BAR_PX = 120;

export function render(data) {
  const aq = data.air_quality;
  // As on the TFT: no header at all when there is no data.
  if (!aq) return `<div class="view-body"><p class="message">No data available</p></div>`;
  const colors = namedColors(data);
  const text = aqiTextColor(aq.aqi, data.theme?.active, colors);
  const rows = POLLUTANTS.map(([label, field, max]) => pollutant(label, aq[field], max, colors));
  return `<header class="view-header" style="background:${aqiHeaderColor(aq.aqi, colors)}"><h2>Air Quality</h2></header>
<div class="view-body">
  <div class="row">
    <section class="panel dark">
      <span class="label">US EPA AQI</span>
      <span class="aqi-value" style="color:${text}">${aq.aqi}</span>
      <span class="aqi-category" style="color:${text}">${escapeHtml(aq.category)}</span>
    </section>
    <section class="panel dark">
      <h3 class="panel-title">Pollutants</h3>
      ${rows.join("")}
    </section>
  </div>
  <p class="footer"><span>${escapeHtml(data.location.name)}</span><span>Updated ${time12(aq.updated_at, data.location.timezone)}</span></p>
</div>`;
}

function pollutant(label, value, max, colors) {
  const fraction = Math.min(value / max, 1);
  const fill =
    Math.trunc(TFT_BAR_PX * fraction) > 3
      ? `<span class="pollutant-fill" style="width:${(fraction * 100).toFixed(1)}%;background:${pollutantBarColor(fraction, colors)}"></span>`
      : "";
  return `<div class="pollutant"><span class="pollutant-name">${label}</span><span class="pollutant-bar">${fill}</span><span class="pollutant-value">${fixed(value, 1)}</span></div>`;
}
```

`solar_clock/web/js/views/index.js`:

```js
// Views in the same order as the TFT (solar_clock/views/__init__.py).

import * as airquality from "./airquality.js";
import * as clock from "./clock.js";
import * as weather from "./weather.js";

export const VIEWS = [clock, weather, airquality];
```

- [ ] **Step 4: Run the tests**

Run: `node --test tests/web/*.test.mjs` and `./venv/bin/pytest tests/test_web_page_files.py tests/test_web_contract.py -v`
Expected: JS 37 pass, 0 fail; Python 4 passed.

- [ ] **Step 5: Commit**

```bash
git add solar_clock/web/js/views/ tests/web/
git commit -m "Add Weather and Air Quality views to the web page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Solar Details and Moon views

**Files:**
- Create: `solar_clock/web/js/views/solar.js`, `solar_clock/web/js/views/moon.js`, `tests/web/solar.test.mjs`, `tests/web/moon.test.mjs`
- Modify: `solar_clock/web/js/views/index.js`, `tests/web/views.test.mjs` (the order assertion)

**Interfaces:**
- Consumes: as in Task 7.
- Produces:
  - Views `solar` ("Solar Details") and `moon` ("Moon Phase"). The phase 1 order is `clock, weather, airquality, solar, moon`.
  - `moon.js` also exports `moonShadow(phase)`.

TFT behaviours these views copy (from `solar.py` and `moon.py`):
- **Solar Details:**
  - Sunrise and Sunset times use the sun accent, Dusk the warm accent, and Dawn and Solar Noon the secondary colour.
  - A golden-hour range reads "6:52 - 7:47 AM".
  - The day length here is not zero-padded ("11h 5m"); the Clock view pads it ("11h 05m").
  - The change shows only when non-zero: sun accent when positive, `PURPLE` otherwise, formatted like "-2.1m vs yday".
- **Moon:** the shadow is an ellipse of width `int(|phase − 0.5| × 200)`, on the left while waxing and on the right while waning. A new moon is fully dark; a full moon (0.47–0.53) has no shadow.

- [ ] **Step 1: Write the failing tests**

`tests/web/solar.test.mjs`:

```js
import { test } from "node:test";

import { render } from "../../solar_clock/web/js/views/solar.js";
import { NOW, assertShows, sampleNow } from "./fixtures.mjs";

test("solar view matches the TFT's text", () => {
  assertShows(render(sampleNow(), NOW), [
    "Dawn", "6:42 AM", "Solar Noon", "12:52 PM", "Dusk", "7:01 PM",
    "6:52 - 7:47 AM", "5:56 - 6:51 PM", "El: 31.4°", "Az: 223°", "11h 30m",
    "-2.1m vs yday", "color:#9370db", "Sunset", "in 3h 23m",
  ]);
});

test("without sun data it shows the TFT message", () => {
  const data = sampleNow();
  data.sun = null;
  assertShows(render(data, NOW), ["Solar data unavailable"]);
});
```

`tests/web/moon.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { moonShadow, render } from "../../solar_clock/web/js/views/moon.js";
import { NOW, assertShows, sampleNow } from "./fixtures.mjs";

test("moon view matches the TFT's text", () => {
  assertShows(render(sampleNow(), NOW), [
    "14%", "Waning Crescent", "3:41 AM", "5:20 PM", "Oct 10", "2d", "Oct 26", "18d",
    "width:89.0%",
  ]);
});

test("without lunar data it shows the TFT message", () => {
  const data = sampleNow();
  data.moon = null;
  assertShows(render(data, NOW), ["Lunar data unavailable"]);
});

test("the shadow follows MoonView's rules", () => {
  assert.match(moonShadow(0.01), /<circle/); // new moon: fully dark
  assert.equal(moonShadow(0.5), ""); // full moon: no shadow
  // First quarter: a 50-wide shadow on the left half.
  assert.equal(moonShadow(0.25), '<ellipse cx="30" cy="55" rx="25" ry="50" fill="#1e1e1e"/>');
  // Waning crescent (0.89): on the right, int(0.39 * 200) = 78 wide.
  assert.equal(moonShadow(0.89), '<ellipse cx="66" cy="55" rx="39" ry="50" fill="#1e1e1e"/>');
});
```

In `tests/web/views.test.mjs`, change the order assertion to the final phase 1 list:

```js
  assert.deepEqual(VIEWS.map((v) => v.name), ["clock", "weather", "airquality", "solar", "moon"]);
```

- [ ] **Step 2: Run them and watch them fail**

Run: `node --test tests/web/*.test.mjs`
Expected: `solar.test.mjs` and `moon.test.mjs` fail with `ERR_MODULE_NOT_FOUND`, and the `views.test.mjs` order test fails.

- [ ] **Step 3: Implement.** `solar_clock/web/js/views/solar.js`:

```js
// Solar Details view: mirrors solar_clock/views/solar.py.

import { countdownHM, dayLengthText, escapeHtml, fixed, time12, time12Bare } from "../format.js";
import { namedColors } from "../theme.js";

export const name = "solar";
export const title = "Solar Details";

export function render(data, now) {
  const colors = namedColors(data);
  const header = `<header class="view-header" style="background:${colors.ORANGE}"><h2>Solar Details</h2></header>`;
  const sun = data.sun;
  if (!sun) return `${header}<div class="view-body"><p class="message">Solar data unavailable</p></div>`;
  const tz = data.location.timezone;
  const t = sun.times;
  return `${header}
<div class="view-body">
  <div class="times-grid">
    <div>${event("Dawn", t.dawn, "secondary", tz)}${event("Sunrise", t.sunrise, "sun", tz)}${event("Solar Noon", t.noon, "secondary", tz)}</div>
    <div>${event("Sunset", t.sunset, "sun", tz)}${event("Dusk", t.dusk, "warm", tz)}</div>
  </div>
  ${goldenHour(sun.golden_hour, tz)}
  <div class="row">
    ${positionPanel(sun.position)}
    ${dayLengthPanel(sun, colors)}
    ${nextEventPanel(sun.next_event, now)}
  </div>
</div>`;
}

function event(label, at, tone, tz) {
  return `<div class="stat"><span class="label">${label}</span><span class="value ${tone}">${time12(at, tz)}</span></div>`;
}

function goldenHour(golden, tz) {
  const range = (span) => `${time12Bare(span.start, tz)} - ${time12(span.end, tz)}`;
  const morning = golden.morning
    ? `<p class="golden-row"><span class="label">Morning:</span> <span class="sun">${range(golden.morning)}</span></p>`
    : "";
  const evening = golden.evening
    ? `<p class="golden-row"><span class="label">Evening:</span> <span class="warm">${range(golden.evening)}</span></p>`
    : "";
  return `<section class="golden"><h3>Golden Hour</h3>${morning}${evening}</section>`;
}

function positionPanel(position) {
  const body = position
    ? `<span class="value sun">El: ${fixed(position.elevation, 1)}°</span><span class="secondary small">Az: ${fixed(position.azimuth)}°</span>`
    : "";
  return `<section class="panel"><span class="label">Sun Position</span>${body}</section>`;
}

function dayLengthPanel(sun, colors) {
  const length = sun.day_length_hours
    ? `<span class="value">${dayLengthText(sun.day_length_hours)}</span>`
    : "";
  const change = sun.day_length_change_min;
  const changeText = change
    ? `<span class="small" style="color:${change > 0 ? "var(--accent-sun)" : colors.PURPLE}">${change > 0 ? "+" : ""}${fixed(change, 1)}m vs yday</span>`
    : "";
  return `<section class="panel"><span class="label">Day Length</span>${length}${changeText}</section>`;
}

function nextEventPanel(next, now) {
  const left = next ? countdownHM(next.at, now) : null;
  const body = left
    ? `<span class="value warm">${escapeHtml(next.name)}</span><span class="secondary small">in ${left.h}h ${left.m}m</span>`
    : "";
  return `<section class="panel"><span class="label">Next Event</span>${body}</section>`;
}
```

`solar_clock/web/js/views/moon.js`:

```js
// Moon Phase view: mirrors solar_clock/views/moon.py.

import { escapeHtml, fixed, shortDate, time12 } from "../format.js";
import { namedColors } from "../theme.js";

export const name = "moon";
export const title = "Moon Phase";

const R = 50; // disc radius, as on the TFT
const C = 55; // disc centre in a 110 x 110 viewBox
const SHADOW = "#1e1e1e"; // (30, 30, 30), the TFT's shadow colour

export function render(data) {
  const colors = namedColors(data);
  const header = `<header class="view-header" style="background:${colors.PURPLE}"><h2>Moon Phase</h2></header>`;
  const moon = data.moon;
  if (!moon) return `${header}<div class="view-body"><p class="message">Lunar data unavailable</p></div>`;
  const tz = data.location.timezone;
  const p = moon.phase;
  return `${header}
<div class="view-body">
  <div class="moon-top">
    ${moonDisc(p.phase, colors)}
    <div><span class="moon-illum">${fixed(p.illumination)}%</span><span class="moon block">${escapeHtml(p.phase_name)}</span></div>
  </div>
  <div class="row">
    ${timeBox("Moonrise", moon.times?.moonrise, tz)}
    ${timeBox("Moonset", moon.times?.moonset, tz)}
    <section class="panel boxed"><span class="label">Lunar Cycle</span>
      <span class="cycle"><span class="cycle-fill" style="width:${(p.phase * 100).toFixed(1)}%;background:${colors.PURPLE}"></span><span class="cycle-full"></span></span>
    </section>
  </div>
  <div class="row">
    <section class="panel"><span class="label">New Moon</span><span class="value">${shortDate(p.next_new)} <span class="secondary small">${p.days_to_new}d</span></span></section>
    <section class="panel"><span class="label">Full Moon</span><span class="value moon">${shortDate(p.next_full)} <span class="secondary small">${p.days_to_full}d</span></span></section>
  </div>
</div>`;
}

function timeBox(label, at, tz) {
  const value = at ? `<span class="value">${time12(at, tz)}</span>` : "";
  return `<section class="panel boxed"><span class="label">${label}</span>${value}</section>`;
}

function moonDisc(phase, colors) {
  return `<svg class="moon-disc" viewBox="0 0 110 110" role="img" aria-label="Moon phase">
      <circle cx="${C}" cy="${C}" r="${R}" fill="${colors.MOON_YELLOW}"/>${moonShadow(phase)}
      <circle cx="${C}" cy="${C}" r="${R}" fill="none" style="stroke:var(--text-tertiary)" stroke-width="1"/>
    </svg>`;
}

/** Shadow over the disc, drawn the way MoonView._render_moon_graphic draws it. */
export function moonShadow(phase) {
  if (phase < 0.03 || phase > 0.97) return `<circle cx="${C}" cy="${C}" r="${R}" fill="${SHADOW}"/>`;
  if (phase >= 0.47 && phase <= 0.53) return "";
  // Waxing: shadow on the left; waning: on the right (northern hemisphere).
  const width = Math.trunc(Math.abs(phase - 0.5) * 2 * R * 2);
  const cx = phase < 0.5 ? C - R + width / 2 : C + R - width / 2;
  return `<ellipse cx="${cx}" cy="${C}" rx="${width / 2}" ry="${R}" fill="${SHADOW}"/>`;
}
```

`solar_clock/web/js/views/index.js`:

```js
// Views in the same order as the TFT (solar_clock/views/__init__.py).

import * as airquality from "./airquality.js";
import * as clock from "./clock.js";
import * as moon from "./moon.js";
import * as solar from "./solar.js";
import * as weather from "./weather.js";

export const VIEWS = [clock, weather, airquality, solar, moon];
```

- [ ] **Step 4: Run the tests**

Run: `node --test tests/web/*.test.mjs` and `./venv/bin/pytest`
Expected: JS 42 pass, 0 fail; Python 303 passed, 3 skipped.

- [ ] **Step 5: Commit**

```bash
git add solar_clock/web/js/views/ tests/web/
git commit -m "Add Solar Details and Moon views to the web page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: App icon and manifest

This task follows the spec's "App icon" section: approved idea A, "Sun Path", used as is.

**Files:**
- Create: `tools/make_icons.py`, `solar_clock/web/manifest.webmanifest`
- Create (generated, then committed): `solar_clock/web/icons/` containing `icon.svg`, `favicon-32.png`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png` and `icon-maskable-512.png`
- Modify: `solar_clock/web/index.html` (head links), `tests/test_web_page_files.py` (append icon tests, add two imports)

**Interfaces:**
- Consumes: `StaticSite` and `WEB_DIR`; the Task 6 version of `test_web_page_files.py`.
- Produces: the icon files and manifest at the URLs the spec lists. `index.html` sets `<title>` and `apple-mobile-web-app-title` to "Solar Clock".

- [ ] **Step 1: Write the failing tests.** In `tests/test_web_page_files.py`, add `import json` above `import re`, add `from PIL import Image` after the `pathlib` import (separated by a blank line, as black and isort expect), and append:

```python
ICON_SIZES = {
    "favicon-32.png": 32,
    "apple-touch-icon.png": 180,
    "icon-192.png": 192,
    "icon-512.png": 512,
    "icon-maskable-512.png": 512,
}


def test_index_links_the_icons_and_manifest():
    refs = _index_references()
    for ref in (
        "/icons/icon.svg",
        "/icons/favicon-32.png",
        "/icons/apple-touch-icon.png",
        "/manifest.webmanifest",
    ):
        assert ref in refs, f"index.html does not link {ref}"


def test_manifest_icons_are_served_at_their_declared_size():
    site = StaticSite()
    manifest = json.loads((WEB_DIR / "manifest.webmanifest").read_text())
    assert manifest["name"] == "Solar Clock"
    assert manifest["start_url"] == "/"
    assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])
    for icon in manifest["icons"]:
        resolved = site.resolve(icon["src"])
        assert resolved is not None, f"manifest lists missing {icon['src']}"
        width, height = Image.open(resolved[0]).size
        assert f"{width}x{height}" == icon["sizes"], icon["src"]


def test_icon_files_have_the_spec_sizes():
    for name, size in ICON_SIZES.items():
        assert Image.open(WEB_DIR / "icons" / name).size == (size, size), name
    assert (WEB_DIR / "icons" / "icon.svg").read_text().startswith("<svg")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `./venv/bin/pytest tests/test_web_page_files.py -v`
Expected: 3 FAILED.
- `index.html does not link /icons/icon.svg`
- `FileNotFoundError` for `manifest.webmanifest`
- `FileNotFoundError` for `icons/favicon-32.png`

- [ ] **Step 3: Implement.** Create `tools/make_icons.py`:
- It draws with Pillow, because homelab has no SVG converter.
- PNGs are drawn at 4× and scaled down for smooth edges.
- It puts a disc at every curve point, because Pillow's own line joins leave visible notches on thick curves.

```python
"""Draw the Solar Clock web page icon: approved idea A, "Sun Path".

Writes solar_clock/web/icons/: icon.svg, favicon-32.png, apple-touch-icon.png,
icon-192.png, icon-512.png and icon-maskable-512.png. The geometry, in
100 x 100 units, is the spec's (docs/superpowers/specs/
2026-10-08-web-page-design.md, "App icon"). PNGs are drawn at 4x and scaled
down for smooth edges; homelab has no SVG rasteriser.

    ./venv/bin/python tools/make_icons.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "solar_clock" / "web" / "icons"
SUPERSAMPLE = 4

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]
Point = tuple[float, float]

BACKGROUND: RGB = (0, 0, 0)
HORIZON: RGB = (128, 128, 128)
DAY: RGB = (255, 220, 50)
NIGHT: RGB = (60, 60, 168)
GLOW: RGB = (255, 140, 0)
SUN_AT: Point = (42, 34.6)


def curve_y(x: float) -> float:
    """The sun's path: above the horizon (y = 62) between x = 30 and x = 80."""
    s = math.sin(2 * math.pi * (x - 30) / 100)
    return 62 - 40 * s if s > 0 else 62 - 22 * s


def curve(x0: float, x1: float, step: float = 0.5) -> list[Point]:
    count = round((x1 - x0) / step)
    return [(x0 + i * step, curve_y(x0 + i * step)) for i in range(count + 1)]


# (points, colour, stroke width), drawn in this order
SEGMENTS: list[tuple[list[Point], RGB, float]] = [
    (curve(8, 30), NIGHT, 4.5),
    (curve(80, 92), NIGHT, 4.5),
    (curve(30, 80), DAY, 5.0),
]


def hex_color(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def svg() -> str:
    def path(points: list[Point]) -> str:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">',
        f'<rect width="100" height="100" fill="{hex_color(BACKGROUND)}"/>',
        f'<line x1="6" y1="62" x2="94" y2="62" stroke="{hex_color(HORIZON)}" stroke-width="2.5"/>',
    ]
    for points, colour, width in SEGMENTS:
        lines.append(
            f'<path d="{path(points)}" fill="none" stroke="{hex_color(colour)}" '
            f'stroke-width="{width:g}" stroke-linecap="round"/>'
        )
    x, y = SUN_AT
    lines.append(
        f'<circle cx="{x:g}" cy="{y:g}" r="11" fill="{hex_color(GLOW)}" opacity="0.35"/>'
    )
    lines.append(f'<circle cx="{x:g}" cy="{y:g}" r="7.5" fill="{hex_color(DAY)}"/>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def png(size: int, scale: float = 1.0) -> Image.Image:
    """The icon at `size` px; `scale` < 1 shrinks the picture about the centre."""
    big = size * SUPERSAMPLE
    unit = big / 100

    def at(x: float, y: float) -> Point:
        return (((x - 50) * scale + 50) * unit, ((y - 50) * scale + 50) * unit)

    def px(length: float) -> float:
        return length * scale * unit

    def disc(
        draw: ImageDraw.ImageDraw, centre: Point, radius: float, fill: RGBA | RGB
    ) -> None:
        cx, cy = centre
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=fill)

    image = Image.new("RGBA", (big, big), BACKGROUND + (255,))
    draw = ImageDraw.Draw(image)
    draw.line([at(6, 62), at(94, 62)], fill=HORIZON, width=max(1, round(px(2.5))))
    for points, colour, width in SEGMENTS:
        scaled = [at(x, y) for x, y in points]
        draw.line(scaled, fill=colour, width=max(1, round(px(width))))
        for point in scaled:  # round joins and caps; Pillow's own joins notch
            disc(draw, point, px(width) / 2, colour)

    glow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    disc(ImageDraw.Draw(glow), at(*SUN_AT), px(11), GLOW + (round(0.35 * 255),))
    image = Image.alpha_composite(image, glow)
    disc(ImageDraw.Draw(image), at(*SUN_AT), px(7.5), DAY)
    return image.resize((size, size), Image.Resampling.LANCZOS).convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon.svg").write_text(svg())
    outputs = {
        "favicon-32.png": png(32),
        "apple-touch-icon.png": png(180),
        "icon-192.png": png(192),
        "icon-512.png": png(512),
        "icon-maskable-512.png": png(512, scale=0.8),
    }
    for name, image in outputs.items():
        image.save(OUT / name, optimize=True)
    print(f"Wrote {len(outputs) + 1} files to {OUT}")


if __name__ == "__main__":
    main()
```

Generate the files and look at one. The 512 px icon should be the approved Sun Path picture: a black square, grey horizon, yellow day arc, navy night ends, and the sun with an orange glow at the upper left of the arc.

```bash
./venv/bin/python tools/make_icons.py
ls -la solar_clock/web/icons/
```

Create `solar_clock/web/manifest.webmanifest`:

```json
{
  "name": "Solar Clock",
  "short_name": "Solar Clock",
  "start_url": "/",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" },
    {
      "src": "/icons/icon-maskable-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ]
}
```

In `solar_clock/web/index.html`, replace the `<title>` line with:

```html
<title>Solar Clock</title>
<meta name="apple-mobile-web-app-title" content="Solar Clock">
<link rel="icon" href="/icons/icon.svg" type="image/svg+xml">
<link rel="icon" href="/icons/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
```

- [ ] **Step 4: Run the tests**

Run: `./venv/bin/pytest tests/test_web_page_files.py -v`, then `./venv/bin/pytest` and `node --test tests/web/*.test.mjs`
Expected: 5 passed; full Python suite 306 passed, 3 skipped; JS 42 pass.

- [ ] **Step 5: Extra gates, lint, commit**

```bash
./venv/bin/mypy --strict --ignore-missing-imports --follow-imports=silent tools/make_icons.py
<scratchpad>/ruffenv/bin/ruff check --no-cache --target-version py39 tools/make_icons.py tests/test_web_page_files.py
./venv/bin/black --check solar_clock tests tools/make_icons.py && ./venv/bin/flake8 solar_clock tests tools/make_icons.py --max-line-length=100 --ignore=E501,W503
git add tools/make_icons.py solar_clock/web/icons/ solar_clock/web/manifest.webmanifest solar_clock/web/index.html tests/test_web_page_files.py
git commit -m "Add the Sun Path app icon and web manifest" -m "Home-screen, desktop-shortcut and tab icons drawn by tools/make_icons.py from the spec's geometry." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Docs, full verification and proof that the TFT is unchanged

**Files:**
- Modify: `README.md`, `CLAUDE.md`
- Scratch only, not committed: `<scratchpad>/parity/render_tft.py` and `compare.py`

- [ ] **Step 1: README.md**

Under `### Additional Features`, add the bullet:

```markdown
- Web page with the same views for phones and laptops on your home network
```

After the `## HTTP API` section's examples block, before `## Hardware Requirements`, insert:

````markdown
## Web Page

The clock serves a phone-friendly page with its views at `http://clock.local:8080/`
(home network only; the HTTP server must bind to `0.0.0.0`). Swipe, tap the arrows
or use the arrow keys to change views. This never changes what the clock's own
screen shows. Colours follow the clock's day/night theme. Use your browser's
"Add to Home Screen" (phone) or "Create shortcut" (desktop) for an app icon.

Views: Clock, Weather, Air Quality, Solar Details and Moon Phase.
````

In the HTTP API endpoint table, add two rows:

```markdown
| `GET /` | The web page |
| `GET /api/now` | JSON behind the web page (read-only) |
```

In `## Project Structure`, add under `solar_clock/`:

```text
│   ├── web_api.py           # /api/now data for the web page
│   ├── web_static.py        # Serves the web page's files
│   ├── web/                 # The web page (HTML, CSS, JavaScript modules, icons)
```

In `## Development`, add before `### Code Style`:

````markdown
### Web Page
The page lives in `solar_clock/web/`: plain JavaScript modules, no build step.
```bash
# Serve it without a display (port 8091); --sample-weather fills the weather views
./venv/bin/python -m tools.web_preview --config config.example.json --sample-weather
# JavaScript tests (Node 18+)
node --test tests/web/*.test.mjs
# Redraw the app icon
./venv/bin/python tools/make_icons.py
```
````

- [ ] **Step 2: CLAUDE.md.** Add two rows to the HTTP Endpoints table:

```markdown
| `/` | The web page (phone-friendly copy of the views) |
| `/api/now` | JSON for the web page (read-only) |
```

Add this section before `## Configuration`:

```markdown
## Web Page

`http://clock.local:8080/` serves a browser copy of the views from `solar_clock/web/`.

- The page and `/api/now` must never change clock state: no `ViewManager` calls, never `set_mode` on the clock's ThemeManager.
- `HTTPServer` must stay single-threaded: `web_api.py` keeps its own SolarProvider/LunarProvider, which are not thread-safe.
- Each TFT view has a JavaScript twin in `solar_clock/web/js/views/`. When you change a TFT view's text, format or colours, change its twin too and run `node --test tests/web/*.test.mjs`.
- Preview without a display: `./venv/bin/python -m tools.web_preview --config config.example.json --sample-weather` (port 8091).
```

- [ ] **Step 3: Full checks**

```bash
./venv/bin/pytest
node --test tests/web/*.test.mjs
./venv/bin/black --check solar_clock tests && ./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503 && ./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
./venv/bin/mypy --strict --ignore-missing-imports --follow-imports=silent solar_clock/web_api.py solar_clock/web_static.py tools/make_icons.py tools/web_preview.py
<scratchpad>/ruffenv/bin/ruff check --no-cache --target-version py39 solar_clock/web_api.py solar_clock/web_static.py tools/make_icons.py tools/web_preview.py tests/test_web_api.py tests/test_web_page_files.py tests/test_web_contract.py
```

Expected: Python 306 passed, 3 skipped; JS 42 pass; every linter clean.

- [ ] **Step 4: TFT proof 1.** The protected files are unchanged, and so is `SolarClock.run()`.

```bash
git diff --stat main -- solar_clock/views solar_clock/display.py solar_clock/touch_handler.py   # must print nothing
./venv/bin/python - <<'EOF'
import ast, subprocess
def run_body(ref):
    src = subprocess.run(["git", "show", f"{ref}:solar_clock/main.py"], capture_output=True, text=True, check=True).stdout
    cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "SolarClock")
    return ast.dump(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "run"))
assert run_body("main") == run_body("HEAD"), "SolarClock.run() changed"
print("SolarClock.run() unchanged")
EOF
```

- [ ] **Step 5: TFT proof 2: pixel parity.** Render all 9 views in both themes at `main` (before phase 1) and at the branch head, with the time frozen at Thu 8 Oct 2026 3:12 PM and identical fixed data. Every image must be identical. Save the two scripts below in `<scratchpad>/parity/`; they are deliberately not committed.

`<scratchpad>/parity/render_tft.py`:

```python
"""Render all 9 TFT views from one checkout with frozen time and fixed data.

One-off TFT parity check for the web page work (not committed). Usage:
    python render_tft.py <repo checkout> <output dir>
Renders each view in the night and day themes to <output dir>/<theme>-<n>-<name>.png.
"""

import datetime as real_datetime
import math
import sys
import types
from pathlib import Path
from zoneinfo import ZoneInfo

repo, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
sys.path.insert(0, str(repo))

import solar_clock  # noqa: E402

assert Path(solar_clock.__file__).resolve().is_relative_to(repo), solar_clock.__file__

from solar_clock.config import _dict_to_config  # noqa: E402
from solar_clock.data.lunar import (  # noqa: E402
    AnalemmaPoint,
    MoonPhase,
    MoonTimes,
    SolsticeEquinox,
)
from solar_clock.data.solar import GoldenHour, SolarPosition, SunTimes  # noqa: E402
from solar_clock.data.weather import (  # noqa: E402
    AirQuality,
    CurrentWeather,
    DailyForecast,
)
from solar_clock.views import VIEW_CLASSES  # noqa: E402
from solar_clock.views import base as views_base  # noqa: E402
from solar_clock.views.base import DataProviders  # noqa: E402
from solar_clock.views.theme import ThemeManager  # noqa: E402

TZ = ZoneInfo("America/New_York")
FIXED = real_datetime.datetime(2026, 10, 8, 15, 12, 0, tzinfo=TZ)


class FrozenDateTime(real_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED.replace(tzinfo=None) if tz is None else FIXED.astimezone(tz)


class FrozenDate(real_datetime.date):
    @classmethod
    def today(cls):
        return FIXED.date()


FROZEN = types.SimpleNamespace(
    datetime=FrozenDateTime,
    date=FrozenDate,
    timedelta=real_datetime.timedelta,
    time=real_datetime.time,
    timezone=real_datetime.timezone,
)


def at(hour, minute):
    return real_datetime.datetime(2026, 10, 8, hour, minute, tzinfo=TZ)


class Solar:
    def get_sun_times(self, date=None):
        return SunTimes(at(6, 42), at(7, 8), at(12, 52), at(18, 35), at(19, 1))

    def get_day_length(self, date=None):
        day = (date or FIXED.date()).timetuple().tm_yday
        return 12 + 3 * math.sin(2 * math.pi * (day - 80) / 365)

    def get_day_length_change(self):
        return -2.13

    def get_solar_position(self, dt=None):
        dt = dt or FIXED
        hours = dt.astimezone(TZ).hour + dt.astimezone(TZ).minute / 60
        return SolarPosition(
            elevation=45 * math.sin(math.pi * (hours - 7) / 12), azimuth=15 * hours
        )

    def get_golden_hour(self, date=None):
        return GoldenHour(at(6, 52), at(7, 47)), GoldenHour(at(17, 56), at(18, 51))

    def get_next_solar_event(self):
        return "Sunset", at(18, 35)


class Lunar:
    available = True

    def get_moon_phase(self):
        return MoonPhase(
            0.89,
            14.2,
            "Waning Crescent",
            real_datetime.date(2026, 10, 10),
            real_datetime.date(2026, 10, 26),
            2,
            18,
        )

    def get_moon_times(self, date=None):
        return MoonTimes(at(3, 41), at(17, 20))

    def get_solstice_equinox(self, year):
        d = real_datetime.date
        return SolsticeEquinox(d(year, 3, 20), d(year, 6, 21), d(year, 9, 22), d(year, 12, 21))

    def get_analemma_data(self):
        start = real_datetime.date(2026, 1, 1)
        return [
            AnalemmaPoint(
                elevation=50 + 23 * math.sin(2 * math.pi * (w * 7 - 80) / 365),
                equation_of_time=10 * math.sin(4 * math.pi * w * 7 / 365),
                date=start + real_datetime.timedelta(days=7 * w),
            )
            for w in range(53)
        ]

    def get_equation_of_time(self, date=None):
        return 12.3


class Weather:
    def get_current_weather(self):
        return CurrentWeather(64.5, 63.2, 58, "Scattered Clouds", 7.4, "WSW")

    def get_forecast(self, days=3):
        return [
            DailyForecast("2026-10-08", 66.1, 51.3, 10),
            DailyForecast("2026-10-09", 61.0, 48.8, 40),
            DailyForecast("2026-10-10", 58.4, 45.0, 0),
        ][:days]

    def get_air_quality(self):
        return AirQuality(42, "Good", 10.1, 18.4, 61.2, 12.7, 1.9, 230.5, FIXED.timestamp())


config = _dict_to_config(
    {"location": {"name": "Test City", "timezone": "America/New_York", "latitude": 40.7, "longitude": -74.0}}
)
providers = DataProviders(weather=Weather(), solar=Solar(), lunar=Lunar())
modules = {sys.modules[cls.__module__] for cls in VIEW_CLASSES} | {views_base}
for module in modules:
    if hasattr(module, "datetime"):
        module.datetime = FROZEN

out.mkdir(parents=True, exist_ok=True)
for mode in ("night", "day"):
    ThemeManager.initialize(None).set_mode(mode)
    for index, cls in enumerate(VIEW_CLASSES):
        image = cls(config, providers).render(index, len(VIEW_CLASSES))
        image.save(out / f"{mode}-{index + 1}-{cls.name}.png")
print(f"rendered {2 * len(VIEW_CLASSES)} images from {repo}")
```

`<scratchpad>/parity/compare.py`:

```python
"""Compare two folders of TFT renders pixel by pixel. Exit 1 on any difference."""

import sys
from pathlib import Path

from PIL import Image, ImageChops

base, head = Path(sys.argv[1]), Path(sys.argv[2])
names = sorted(p.name for p in base.glob("*.png"))
assert names == sorted(p.name for p in head.glob("*.png")), "different file sets"
assert len(names) == 18, f"expected 18 renders, found {len(names)}"
changed = [n for n in names if ImageChops.difference(
    Image.open(base / n).convert("RGB"), Image.open(head / n).convert("RGB")
).getbbox() is not None]
print(f"{len(names) - len(changed)}/{len(names)} identical")
for name in changed:
    print("DIFFERENT:", name)
sys.exit(1 if changed else 0)
```

Run:

```bash
P=<scratchpad>/parity
git worktree add "$P/base" main
./venv/bin/python -I "$P/render_tft.py" "$P/base" "$P/out-base"
./venv/bin/python -I "$P/render_tft.py" "$PWD" "$P/out-head"
./venv/bin/python -I "$P/compare.py" "$P/out-base" "$P/out-head"
git worktree remove "$P/base"
```

Expected: `18/18 identical`, exit 0.
- Any `DIFFERENT:` line means phase 1 changed the TFT. Stop and find out why before going further.
- Optionally prove the check has teeth: in a throwaway copy, change one colour in `views/theme.py` by one unit. It must report differences; when the plan was checked, it reported 6.

- [ ] **Step 6: Peter's look on his phone (STOP and wait)**
- Start the preview on all interfaces: `./venv/bin/python -m tools.web_preview --config config.example.json --sample-weather --bind 0.0.0.0` (background it and save the PID as before).
- Ask Peter to open `http://<homelab's address>:8091/` on his phone. Get the address with `hostname -I`, which changes, so read it each time.
- Ask him to check: each of the 5 views in portrait and landscape; swiping; the day theme (restart the preview with `--theme day`) and the night theme; and that nothing is cut off or overlapping.
- Fix what he reports in the owning task's files, re-run Step 3, and commit each fix with its own message.
- Stop the preview by PID when done.

- [ ] **Step 7: Commit the docs**

```bash
git add README.md CLAUDE.md
git commit -m "Document the web page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Merge, push, deploy and check on clock.local (gated)

- [ ] **Step 1: Ask Peter for the go-ahead (STOP).** Summarise the branch: commits, test counts, the parity result and his phone check. Pushing to GitHub and restarting the clock both need his explicit yes.

- [ ] **Step 2: Capture the "before" state**

```bash
curl -s http://clock.local:8080/view                     # e.g. "sunpath (4/9)": note the view
curl -s -o <scratchpad>/before.png http://clock.local:8080/screenshot
ssh clock.local 'ps -o rss= -p "$(systemctl show -p MainPID --value solar-clock)"'   # KB
```

- [ ] **Step 3: Merge and push.** The pre-push hook runs every lint hook and pytest.

```bash
git switch main
git merge --ff-only web-page-phase1
git push origin main
```

- [ ] **Step 4: Deploy and wait for the service**

```bash
ssh clock.local 'cd ~/solar-clock && git pull --ff-only && sudo systemctl restart solar-clock'
timeout 60 bash -c 'until curl -sf http://clock.local:8080/health >/dev/null; do sleep 1; done' && echo up
```

If your environment blocks foreground `sleep`, run that wait through the Monitor tool.

- [ ] **Step 5: Check it**

```bash
ssh clock.local 'systemctl is-active solar-clock; journalctl -u solar-clock --since "-3 min" --no-pager | grep -E "Web page|ERROR|Traceback"'
curl -s -o /dev/null -w "/ %{http_code} %{content_type}\n" http://clock.local:8080/
curl -s http://clock.local:8080/api/now | python3 -m json.tool | head -30
curl -s -o /dev/null -w "/../config.json %{http_code}\n" --path-as-is "http://clock.local:8080/../config.json"
```

Expected:
- `active`, and a log line `Web page: 19 files from /home/pi/solar-clock/solar_clock/web`, with no `ERROR` or `Traceback`.
- `/` answers `200 text/html; charset=utf-8`; the JSON shows real sun, weather and moon data; `/../config.json` answers `404`.

- [ ] **Step 6: Put the clock back on the view it showed, then compare.** A restart resets the clock to its default view.
- If Step 2 showed view *k* of 9 and the clock now shows view 1, call `curl -s http://clock.local:8080/next` *k − 1* times. That is the same as pressing the arrow on the clock, and it restores what Peter had on screen.
- Then run `curl -s -o <scratchpad>/after.png http://clock.local:8080/screenshot`.
- Look at `before.png` and `after.png`: apart from the time and live values, they must match.

- [ ] **Step 7: Memory, and Peter's checks**
- Record the RSS again now, and once more after about an hour with the page open on Peter's phone. Report both against Step 2.
- Ask Peter to:
  - swipe the physical screen once, to confirm touch still works;
  - open `http://clock.local:8080/` on his phone;
  - add it to his home screen and confirm the Sun Path icon appears;
  - flip through the five views.

- [ ] **Step 8: Wrap up**
- Phase 1 is done when the checks above pass and Peter confirms.
- Delete the local branch `web-page-phase1` only if he agrees.
- Then write the phase 2 plan.
