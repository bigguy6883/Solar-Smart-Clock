# Code Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all bugs and efficiency issues identified in the code review of the Solar Smart Clock project.

**Architecture:** Fixes are grouped by severity. Group 1 addresses correctness bugs that produce wrong output or broken behavior. Group 2 fixes efficiency problems. Group 3 handles minor issues and cleanup. Each task is independent unless noted.

**Tech Stack:** Python 3, PIL/Pillow, astral, ephem, requests, threading, evdev. Tests use pytest with mocks. Run tests with `./venv/bin/pytest tests/ -v`.

---

## Group 1 — Critical Bugs

---

### Task 1: Guard negative countdown deltas (3 locations)

Fixes issue where a solar event passes between the data fetch and the render, causing negative hours/minutes in the countdown display (e.g. "Sunrise in -1h -47m").

**Files:**
- Modify: `solar_clock/views/clock.py:244-266`
- Modify: `solar_clock/views/solar.py:153-167`
- Modify: `solar_clock/views/sunpath.py:183-195`
- Test: `tests/test_views.py`

**Step 1: Write the failing test**

Add to `tests/test_views.py` (or a new `tests/test_clock_view.py` if that file is already large):

```python
def test_negative_countdown_not_rendered(mock_providers, monkeypatch):
    """Countdown must not render when event_time is in the past."""
    import datetime
    from solar_clock.views.clock import ClockView
    from unittest.mock import MagicMock

    # Make get_next_solar_event return an event 5 seconds in the past
    past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
    mock_providers.solar.get_next_solar_event.return_value = ("Sunrise", past_time)

    # Render and capture the draw calls
    view = ClockView.__new__(ClockView)
    view.providers = mock_providers
    # (wire up remaining view attributes as needed for the fixture)

    image = view.render()
    # Convert to bytes and confirm "Sunrise in -" does NOT appear
    # (simplest check: render without exception and assert no negative string)
    import io
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    assert buf.tell() > 0  # rendered without crash

    # Stricter: monkeypatch draw.text to collect strings
    drawn_texts = []
    real_render = view._render_day_progress
    def patched(draw, y):
        orig_text = draw.text
        def capture(pos, text, **kwargs):
            drawn_texts.append(text)
            return orig_text(pos, text, **kwargs)
        draw.text = capture
        real_render(draw, y)
    view._render_day_progress = patched
    view.render()
    assert not any("-" in t and "h" in t for t in drawn_texts), \
        f"Negative countdown rendered: {drawn_texts}"
```

**Step 2: Run test to verify it fails**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_views.py -k "negative_countdown" -v
```

Expected: FAIL (negative countdown is currently rendered).

**Step 3: Implement fix in all three locations**

In `solar_clock/views/clock.py`, around line 254, after computing `delta`:

```python
delta = event_time - now_tz
if delta.total_seconds() < 0:
    pass  # event just passed; skip rendering
else:
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    countdown = f"{event_name} in {hours}h {minutes}m"
    countdown_bbox = draw.textbbox((0, 0), countdown, font=font)
    countdown_width = countdown_bbox[2] - countdown_bbox[0]
    draw.text(
        ((self.width - countdown_width) // 2, y + 38),
        countdown,
        fill=theme.text_primary,
        font=font,
    )
```

In `solar_clock/views/solar.py`, around line 158, same pattern — wrap the `hours`/`minutes` block with `if delta.total_seconds() >= 0:`.

In `solar_clock/views/sunpath.py`, around line 185, same pattern.

**Step 4: Run test to verify it passes**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_views.py -k "negative_countdown" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/views/clock.py solar_clock/views/solar.py solar_clock/views/sunpath.py tests/test_views.py
git commit -m "fix: skip countdown render when solar event delta is negative"
```

---

### Task 2: Fix signal handler — wake sleeping main loop on shutdown

When SIGINT/SIGTERM arrives while the main loop is sleeping in `view_changed.wait()`, shutdown is delayed by up to the view's full `update_interval` (up to 3600s for hourly views).

**Files:**
- Modify: `solar_clock/main.py:155-158`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_signal_handler_wakes_main_loop():
    """Signal handler must set view_changed to interrupt the sleep."""
    from unittest.mock import MagicMock, patch
    import threading
    from solar_clock.main import SolarClock

    clock = SolarClock.__new__(SolarClock)
    clock.running = True
    clock.view_manager = MagicMock()
    clock.view_manager.view_changed = threading.Event()

    clock._signal_handler(2, None)  # SIGINT

    assert not clock.running
    assert clock.view_manager.view_changed.is_set(), \
        "view_changed must be set so wait() returns immediately"
```

**Step 2: Run test to verify it fails**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_main.py -k "signal_handler_wakes" -v
```

Expected: FAIL (`view_changed` is not set).

**Step 3: Implement fix**

In `solar_clock/main.py`, replace lines 155–158:

```python
def _signal_handler(self, signum, frame) -> None:
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    self.running = False
    self.view_manager.view_changed.set()  # Wake sleeping main loop immediately
```

**Step 4: Run test**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_main.py -k "signal_handler_wakes" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/main.py tests/test_main.py
git commit -m "fix: wake main loop immediately on shutdown signal"
```

---

### Task 3: Fix missed-wakeup window — move view_changed.clear() before wait()

If a `view_changed.set()` arrives after `wait()` returns but before `clear()`, it is silently discarded, causing one touch/navigation event to be dropped.

**Files:**
- Modify: `solar_clock/main.py:144-148`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_view_changed_clear_before_wait_prevents_missed_wakeup():
    """A set() arriving before clear() must not be lost."""
    import threading

    event = threading.Event()
    results = []

    def simulate_loop(event):
        # Emulate the WRONG order: wait then clear
        event.wait(timeout=0.05)
        # Inject a set() here (simulates a touch arriving in the gap)
        event.set()
        event.clear()  # This clears the injected set — wakeup is lost
        results.append(event.is_set())

    event.clear()
    simulate_loop(event)
    # The injected set was cleared — wakeup lost
    assert results[-1] == False  # noqa: E712 — confirms bug exists

    # Now test correct order: clear THEN wait
    results2 = []
    event2 = threading.Event()

    def simulate_loop_correct(event):
        event.clear()              # clear BEFORE wait
        # Inject a set() here (simulates a touch arriving before wait returns)
        # In the real code this would arrive on another thread; here we pre-set
        event.set()
        event.wait(timeout=0.05)  # returns immediately because set() happened
        results2.append(event.is_set())

    simulate_loop_correct(event2)
    assert results2[-1] == True  # noqa: E712 — wakeup is preserved
```

This test documents the fix. It is illustrative — the real benefit is in production.

**Step 2: Apply the fix**

In `solar_clock/main.py`, change the loop body (around lines 143–148) from:

```python
self.view_manager.view_changed.wait(
    timeout=current_view.update_interval
)
self.view_manager.view_changed.clear()
```

to:

```python
self.view_manager.view_changed.clear()  # clear BEFORE wait
self.view_manager.view_changed.wait(
    timeout=current_view.update_interval
)
```

**Step 3: Run all main tests**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_main.py -v
```

Expected: all PASS.

**Step 4: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/main.py tests/test_main.py
git commit -m "fix: clear view_changed event before wait() to prevent missed wakeups"
```

---

### Task 4: Add render lock to prevent thread-unsafe concurrent rendering

The HTTP server and the main loop both call `render_current()` on separate threads with no synchronization. This is a data race on PIL image objects and provider state.

**Files:**
- Modify: `solar_clock/views/base.py` — `ViewManager` class
- Modify: `solar_clock/main.py` — pass lock when rendering for HTTP
- Test: `tests/test_views.py`

**Step 1: Write the failing test**

```python
def test_render_current_is_thread_safe():
    """Concurrent render_current() calls must not corrupt output."""
    import threading
    from unittest.mock import MagicMock, patch
    from solar_clock.views.base import ViewManager

    mock_view = MagicMock()
    mock_view.render.return_value = MagicMock()  # PIL Image mock
    manager = ViewManager([mock_view], 0)

    errors = []
    def render_loop():
        for _ in range(50):
            try:
                manager.render_current()
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=render_loop) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread-safety errors: {errors}"
    # Also verify lock exists on manager
    assert hasattr(manager, '_render_lock')
```

**Step 2: Run test to verify it fails**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_views.py -k "thread_safe" -v
```

Expected: FAIL (no `_render_lock` attribute).

**Step 3: Add lock to ViewManager**

In `solar_clock/views/base.py`, locate the `ViewManager.__init__` (around line 425 based on grep), add `self._render_lock = threading.Lock()`.

Then in `ViewManager.render_current()`, wrap the body:

```python
def render_current(self) -> Image.Image:
    with self._render_lock:
        return self.views[self.current_index].render()
```

**Step 4: Run test**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_views.py -k "thread_safe" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/views/base.py tests/test_views.py
git commit -m "fix: add render lock to ViewManager to prevent concurrent render data race"
```

---

### Task 5: Fix weather cache partial-state poisoning

When the current weather API call succeeds but the forecast API call fails, `_current_weather` is updated but `_forecast` remains stale. Updates should be committed atomically.

**Files:**
- Modify: `solar_clock/data/weather.py:142-207`
- Test: `tests/test_weather.py`

**Step 1: Write the failing test**

```python
def test_weather_fetch_does_not_update_current_when_forecast_fails(provider):
    """If forecast request fails, neither current nor forecast cache is updated."""
    from unittest.mock import patch, MagicMock
    import requests

    old_weather = provider._current_weather  # None initially

    # Mock: current succeeds, forecast raises HTTPError
    good_resp = MagicMock()
    good_resp.raise_for_status.return_value = None
    good_resp.json.return_value = {
        "main": {"temp": 72, "feels_like": 70, "humidity": 50},
        "weather": [{"description": "clear sky"}],
        "wind": {"speed": 5, "deg": 180},
    }
    bad_resp = MagicMock()
    bad_resp.raise_for_status.side_effect = requests.HTTPError("429")

    def fake_get(url, timeout=10):
        if "forecast" in url:
            return bad_resp
        return good_resp

    with patch("requests.get", side_effect=fake_get):
        provider._fetch_weather()

    # _current_weather must NOT have been updated (still None)
    assert provider._current_weather is old_weather, \
        "_current_weather was updated despite forecast failure"
    assert provider._weather_updated == 0, \
        "_weather_updated timestamp was advanced despite partial failure"
```

**Step 2: Run to verify it fails**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_weather.py -k "partial_state" -v
```

Expected: FAIL (current weather IS updated despite forecast failure).

**Step 3: Implement fix**

In `solar_clock/data/weather.py`, restructure `_fetch_weather` to parse both responses into local variables first, then assign both atomically only if both succeed:

```python
def _fetch_weather(self) -> None:
    """Fetch current weather and forecast from API concurrently."""
    if not self.api_key:
        logger.warning("No API key configured, skipping weather fetch")
        return

    current_url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={self.latitude}&lon={self.longitude}"
        f"&appid={self.api_key}&units={self.units}"
    )
    forecast_url = (
        f"https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={self.latitude}&lon={self.longitude}"
        f"&appid={self.api_key}&units={self.units}"
    )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            current_future = executor.submit(requests.get, current_url, timeout=10)
            forecast_future = executor.submit(requests.get, forecast_url, timeout=10)
            current_resp = current_future.result()
            forecast_resp = forecast_future.result()

        current_resp.raise_for_status()
        current_data = current_resp.json()
        main = current_data.get("main", {})
        weather_list = current_data.get("weather", [{}])
        wind = current_data.get("wind", {})
        new_weather = CurrentWeather(
            temperature=main.get("temp", 0),
            feels_like=main.get("feels_like", 0),
            humidity=main.get("humidity", 0),
            description=(
                weather_list[0].get("description", "Unknown").title()
                if weather_list
                else "Unknown"
            ),
            wind_speed=wind.get("speed", 0),
            wind_direction=self._degrees_to_compass(wind.get("deg", 0)),
        )

        forecast_resp.raise_for_status()
        forecast_data = forecast_resp.json()
        new_forecast = self._parse_forecast(forecast_data)

        # Commit both atomically — only if both succeeded
        self._current_weather = new_weather
        self._forecast = new_forecast
        self._weather_updated = time.time()
        logger.debug("Weather data updated successfully")

    except requests.Timeout:
        logger.warning("Weather API request timed out")
    except requests.HTTPError as e:
        logger.warning(f"Weather API HTTP error: {e}")
    except requests.RequestException as e:
        logger.warning(f"Weather API request failed: {e}")
    except (KeyError, ValueError) as e:
        logger.warning(f"Failed to parse weather data: {e}")
```

**Step 4: Run test**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_weather.py -k "partial_state" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/data/weather.py tests/test_weather.py
git commit -m "fix: commit weather and forecast cache atomically to prevent split state"
```

---

## Group 2 — Efficiency

---

### Task 6: Cache get_sun_times() results in SolarProvider (daily cache)

`get_sun_times()` calls `astral.sun.sun()` every invocation. On `ClockView` (1-second updates), this is called 3+ times per second — once from `get_time_header_color()`, once from `_render_sun_info()`, and once from `get_day_length()`. Results are valid all day.

**Files:**
- Modify: `solar_clock/data/solar.py`
- Test: `tests/test_solar.py`

**Step 1: Write the failing test**

```python
def test_get_sun_times_called_once_per_day(provider, monkeypatch):
    """get_sun_times() should call astral sun() only once per date."""
    from unittest.mock import patch, call
    import datetime

    call_count = [0]
    real_sun = provider.get_sun_times.__wrapped__ if hasattr(provider.get_sun_times, '__wrapped__') else None

    with patch("solar_clock.data.solar.sun") as mock_sun:
        mock_sun.return_value = {
            "dawn": datetime.datetime(2026, 2, 20, 6, 0, tzinfo=datetime.timezone.utc),
            "sunrise": datetime.datetime(2026, 2, 20, 6, 30, tzinfo=datetime.timezone.utc),
            "noon": datetime.datetime(2026, 2, 20, 12, 0, tzinfo=datetime.timezone.utc),
            "sunset": datetime.datetime(2026, 2, 20, 18, 0, tzinfo=datetime.timezone.utc),
            "dusk": datetime.datetime(2026, 2, 20, 18, 30, tzinfo=datetime.timezone.utc),
        }
        today = datetime.date(2026, 2, 20)
        provider.get_sun_times(today)
        provider.get_sun_times(today)
        provider.get_sun_times(today)
        assert mock_sun.call_count == 1, \
            f"Expected 1 astral sun() call, got {mock_sun.call_count}"
```

**Step 2: Run to verify it fails**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_solar.py -k "called_once_per_day" -v
```

Expected: FAIL (sun() is called 3 times).

**Step 3: Add a per-date cache to SolarProvider**

In `solar_clock/data/solar.py`, update `SolarProvider.__init__` to add:

```python
self._sun_times_cache: dict[datetime.date, Optional[SunTimes]] = {}
```

Then update `get_sun_times()`:

```python
def get_sun_times(self, date: Optional[datetime.date] = None) -> Optional[SunTimes]:
    if date is None:
        date = datetime.date.today()

    if date in self._sun_times_cache:
        return self._sun_times_cache[date]

    try:
        s = sun(self.location.observer, date=date, tzinfo=self.location.timezone)
        result = SunTimes(
            dawn=s["dawn"],
            sunrise=s["sunrise"],
            noon=s["noon"],
            sunset=s["sunset"],
            dusk=s["dusk"],
        )
    except ValueError as e:
        logger.warning(f"Could not calculate sun times for {date}: {e}")
        result = None
    except KeyError as e:
        logger.error(f"Missing sun time data: {e}")
        result = None

    # Only cache current day and tomorrow; drop stale entries
    self._sun_times_cache = {
        k: v for k, v in self._sun_times_cache.items()
        if k >= datetime.date.today()
    }
    self._sun_times_cache[date] = result
    return result
```

**Step 4: Run test**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_solar.py -k "called_once_per_day" -v
```

Expected: PASS.

**Step 5: Run full solar test suite**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_solar.py -v
```

Expected: all PASS.

**Step 6: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/data/solar.py tests/test_solar.py
git commit -m "perf: cache get_sun_times() per date to avoid repeated astral calculations"
```

---

### Task 7: Cache get_analemma_data() for the year

`get_analemma_data()` is recomputed from scratch on every hourly render (52 full ephem calculations). The data is constant for the year.

**Files:**
- Modify: `solar_clock/data/lunar.py`
- Test: `tests/test_lunar.py`

**Step 1: Write the failing test**

```python
def test_get_analemma_data_cached_for_year(provider):
    """get_analemma_data() must not recompute if already cached for this year."""
    if not provider.available:
        pytest.skip("ephem not available")

    # First call populates cache
    result1 = provider.get_analemma_data()
    assert len(result1) > 0

    # Patch the inner ephem observer to detect if it's called again
    from unittest.mock import patch
    with patch.object(provider, '_observer') as mock_obs:
        result2 = provider.get_analemma_data()

    # If caching works, _observer was never touched on second call
    mock_obs.next_transit.assert_not_called()
    assert result1 == result2
```

**Step 2: Run to verify it fails**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_lunar.py -k "analemma_cached" -v
```

Expected: FAIL.

**Step 3: Add cache to LunarProvider**

In `solar_clock/data/lunar.py`, add to `__init__`:

```python
self._analemma_cache: Optional[tuple[int, list]] = None  # (year, points)
```

In `get_analemma_data()`, wrap the computation:

```python
def get_analemma_data(self) -> list[AnalemmaPoint]:
    if not EPHEM_AVAILABLE:
        return []

    year = datetime.date.today().year
    if self._analemma_cache is not None and self._analemma_cache[0] == year:
        return self._analemma_cache[1]

    points = []
    try:
        # ... existing computation ...
        self._analemma_cache = (year, points)
        return points
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to calculate analemma: {e}")
        return []
```

**Step 4: Fix get_equation_of_time() to not create a new observer every call**

While in this file, also fix `get_equation_of_time()` (lines 248–253). The prime-meridian observer used there is always identical — create it once in `__init__`:

In `__init__` (after the location observer):
```python
if EPHEM_AVAILABLE:
    # ... existing _observer setup ...
    self._eot_observer = ephem.Observer()
    self._eot_observer.lat = "0"
    self._eot_observer.lon = "0"
    self._eot_observer.elevation = 0
    self._eot_observer.pressure = 0
```

In `get_equation_of_time()`, replace the `observer = ephem.Observer()` block with `self._eot_observer.date = dt`.

**Step 5: Fix get_moon_times() to reuse self._observer**

In `get_moon_times()`, replace lines 158–161:

```python
# Before (creates new observer each call):
observer = ephem.Observer()
observer.lat = str(self.latitude)
observer.lon = str(self.longitude)
observer.date = date.strftime("%Y/%m/%d")
```

With:

```python
# After (reuse shared observer, just update date):
self._observer.date = date.strftime("%Y/%m/%d")
observer = self._observer
```

Note: `self._observer` is shared, so this is safe only within a single-threaded call. Since `LunarProvider` methods are not called concurrently (no lock), this is fine.

**Step 6: Run tests**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_lunar.py -v
```

Expected: all PASS.

**Step 7: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/data/lunar.py tests/test_lunar.py
git commit -m "perf: cache analemma data annually; reuse ephem observers to avoid repeated allocation"
```

---

### Task 8: Replace O(n) text truncation loop with binary search

In `views/weather.py`, the description truncation loop calls `draw.textbbox()` up to 27 times per character removed. Replace with binary search.

**Files:**
- Modify: `solar_clock/views/weather.py:41-51`
- Test: `tests/test_views.py`

**Step 1: Write the failing test**

```python
def test_weather_description_truncation_uses_few_textbbox_calls():
    """Text truncation must call textbbox at most O(log n) times, not O(n)."""
    from unittest.mock import MagicMock, patch
    # This is a code-structure test — we verify the loop is gone
    import inspect
    from solar_clock.views import weather as weather_module
    src = inspect.getsource(weather_module.WeatherView._render_current_conditions
                            if hasattr(weather_module.WeatherView, '_render_current_conditions')
                            else weather_module.WeatherView.render_content)
    # The old O(n) pattern: while loop calling textbbox inside
    assert "while" not in src or "textbbox" not in src.split("while")[1].split("\n")[0], \
        "O(n) truncation loop still present"
```

Alternatively, write a functional test verifying the description is correctly truncated.

**Step 2: Replace the truncation block**

In `solar_clock/views/weather.py`, replace lines 43–51:

```python
# Old O(n) loop:
if desc_bbox[2] - desc_bbox[0] > max_width:
    while (
        len(desc) > 3
        and draw.textbbox((0, 0), desc + "...", font=font_desc)[2] > max_width
    ):
        desc = desc[:-1]
    desc = desc.rstrip() + "..."
```

With binary search:

```python
if desc_bbox[2] - desc_bbox[0] > max_width:
    lo, hi = 3, len(desc)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if draw.textbbox((0, 0), desc[:mid] + "...", font=font_desc)[2] <= max_width:
            lo = mid
        else:
            hi = mid - 1
    desc = desc[:lo].rstrip() + "..."
```

**Step 3: Run tests**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_views.py -v
```

Expected: all PASS.

**Step 4: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/views/weather.py tests/test_views.py
git commit -m "perf: replace O(n) text truncation loop with binary search in WeatherView"
```

---

## Group 3 — Minor Issues

---

### Task 9: Fix touch_start_y falsy-zero bug

`if self.touch_start_y` is falsy when `touch_start_y == 0` (touch at top of screen). Should be `is not None`.

**Files:**
- Modify: `solar_clock/touch_handler.py:194`
- Test: `tests/test_touch_handler.py`

**Step 1: Write the failing test**

```python
def test_dy_computed_correctly_when_touch_start_y_is_zero(handler):
    """dy must not be zero-forced when touch_start_y == 0."""
    handler.touch_start_x = 100
    handler.touch_start_y = 0      # top of screen
    handler.touch_start_time = time.time() - 0.5  # slow drag, won't trigger gesture
    handler.current_x = 100
    handler.current_y = 50         # moved 50px down

    # Capture the logged dy value
    import logging
    log_records = []
    class Capture(logging.Handler):
        def emit(self, record):
            log_records.append(record.getMessage())
    h = Capture()
    logging.getLogger("solar_clock.touch_handler").addHandler(h)

    handler._on_touch_up()

    logging.getLogger("solar_clock.touch_handler").removeHandler(h)

    dy_log = next((r for r in log_records if "dy=" in r), "")
    # With bug: dy=0; with fix: dy=50
    assert "dy=50" in dy_log or "dy=50," in dy_log, \
        f"Expected dy=50 but got: {dy_log}"
```

**Step 2: Run to verify it fails**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_touch_handler.py -k "dy_computed" -v
```

Expected: FAIL.

**Step 3: Implement fix**

In `solar_clock/touch_handler.py`, line 194:

```python
# Before:
dy = self.current_y - self.touch_start_y if self.touch_start_y else 0
# After:
dy = self.current_y - self.touch_start_y if self.touch_start_y is not None else 0
```

**Step 4: Run test**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_touch_handler.py -k "dy_computed" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/touch_handler.py tests/test_touch_handler.py
git commit -m "fix: use 'is not None' check for touch_start_y to handle y=0 touches"
```

---

### Task 10: Move datetime import to module level in base.py

`get_time_header_color()` does `import datetime` inside the method body — called every second.

**Files:**
- Modify: `solar_clock/views/base.py:376`

**Step 1: Check existing imports**

`base.py` already imports `datetime` at the module level (it uses `datetime.datetime` elsewhere). The function-level import is redundant.

**Step 2: Remove function-level import**

In `solar_clock/views/base.py`, find `get_time_header_color()` (around line 376) and delete the `import datetime` line inside it. The module-level import already covers it.

**Step 3: Run tests**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/ -v
```

Expected: all PASS.

**Step 4: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/views/base.py
git commit -m "cleanup: remove redundant function-level datetime import in get_time_header_color"
```

---

### Task 11: Fix _parse_forecast unguarded dict access

`item["main"]["temp"]` in `_parse_forecast` can `KeyError` on a malformed forecast entry, aborting the entire parse silently.

**Files:**
- Modify: `solar_clock/data/weather.py:264`
- Test: `tests/test_weather.py`

**Step 1: Write the failing test**

```python
def test_parse_forecast_handles_missing_main_key(provider):
    """A forecast entry missing 'main' must not abort the entire parse."""
    data = {
        "list": [
            # Normal entry
            {"dt_txt": "2026-02-20 12:00:00", "main": {"temp": 72}, "pop": 0.1},
            # Malformed entry — missing 'main'
            {"dt_txt": "2026-02-20 15:00:00", "pop": 0.2},
            # Normal entry for next day
            {"dt_txt": "2026-02-21 12:00:00", "main": {"temp": 65}, "pop": 0.3},
        ]
    }
    result = provider._parse_forecast(data)
    # Should still have data for both dates
    dates = [f.date for f in result]
    assert "2026-02-20" in dates, "First day was dropped due to malformed entry"
    assert "2026-02-21" in dates, "Second day was dropped due to malformed entry"
```

**Step 2: Run to verify it fails**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_weather.py -k "missing_main_key" -v
```

Expected: FAIL (KeyError aborts parse).

**Step 3: Implement fix**

In `solar_clock/data/weather.py`, line 264, replace:

```python
daily[date]["temps"].append(item["main"]["temp"])
```

With:

```python
temp = item.get("main", {}).get("temp")
if temp is not None:
    daily[date]["temps"].append(temp)
```

**Step 4: Run test**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_weather.py -k "missing_main_key" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/data/weather.py tests/test_weather.py
git commit -m "fix: guard against missing 'main' key in forecast entries"
```

---

### Task 12: Fix forecast day-name string round-trip

`views/weather.py:150` parses `day.date` (already a `%Y-%m-%d` string) into a `datetime` just to call `strftime("%a")`. Add a helper or parse once at the dataclass level.

**Files:**
- Modify: `solar_clock/views/weather.py:149-151`

**Step 1: Apply the fix directly**

Replace:

```python
date = datetime.datetime.strptime(day.date, "%Y-%m-%d")
day_label = date.strftime("%a")
```

With (no import needed, `datetime` is already imported in this file):

```python
day_label = datetime.datetime.strptime(day.date, "%Y-%m-%d").strftime("%a")
```

This is the same call count, but collapsed to one line and makes the intent clear. Alternatively, since we call this at most 1-2 times per render (only for day index >= 2), this is low impact — the main fix is removing the unnecessary intermediate variable.

A better fix: since `day.date` is always `%Y-%m-%d`, just use:

```python
# Parse only the day-of-week without creating an intermediate variable
_, month_day = day.date.rsplit("-", 1)
# But we need weekday name -- keep strptime, just inline it
day_label = datetime.date.fromisoformat(day.date).strftime("%a")
```

`datetime.date.fromisoformat()` is cleaner than `strptime` for `%Y-%m-%d` strings.

**Step 2: Run tests**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_views.py -v
```

Expected: all PASS.

**Step 3: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/views/weather.py
git commit -m "cleanup: use date.fromisoformat() for cleaner weekday name extraction"
```

---

### Task 13: Fix _dataclass_from_dict to not instantiate a throwaway default

`config.py:180` does `defaults = cls()` just to read default values. Field defaults are already available via `dataclasses.fields()`.

**Files:**
- Modify: `solar_clock/config.py:178-184`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
def test_dataclass_from_dict_uses_field_defaults_not_constructor():
    """_dataclass_from_dict should not call cls() to read defaults."""
    from unittest.mock import patch, call
    from solar_clock.config import _dataclass_from_dict, WeatherConfig

    with patch.object(WeatherConfig, '__init__', wraps=WeatherConfig.__init__) as mock_init:
        result = _dataclass_from_dict(WeatherConfig, {"units": "metric"})

    # Should be called exactly once (for the final cls(**kwargs)), not twice
    assert mock_init.call_count == 1, \
        f"Expected 1 constructor call, got {mock_init.call_count} (extra call reads defaults)"
```

**Step 2: Run to verify it fails**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_config.py -k "field_defaults" -v
```

Expected: FAIL (constructor called twice).

**Step 3: Implement fix**

In `solar_clock/config.py`, replace `_dataclass_from_dict`:

```python
import dataclasses

def _dataclass_from_dict(cls, data: dict):
    """Create a dataclass instance from a dict, using field defaults for missing keys."""
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name in data:
            kwargs[f.name] = data[f.name]
        elif f.default is not dataclasses.MISSING:
            kwargs[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            kwargs[f.name] = f.default_factory()
        # If no default, let cls(**kwargs) raise naturally
    return cls(**kwargs)
```

**Step 4: Run test**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/test_config.py -v
```

Expected: all PASS.

**Step 5: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/config.py tests/test_config.py
git commit -m "cleanup: _dataclass_from_dict reads field defaults without constructing throwaway instance"
```

---

### Task 14: Fix fit_text_in_width misleading docstring

`layout_helpers.py:126` — the parameter `max_width` implies pixels but the implementation compares to `len(text)` (character count). Fix the docstring only (the function behavior is intentional character-based; callers needing pixel truncation do so separately).

**Files:**
- Modify: `solar_clock/views/layout_helpers.py:125-144`

**Step 1: Apply fix**

Update the docstring to replace:

```
max_width: Maximum character count
```

With:

```
max_width: Maximum number of characters (not pixels). For pixel-accurate
    truncation use PIL's textbbox directly.
```

And rename the parameter `max_width` → `max_chars` throughout the function (both signature and body):

```python
@staticmethod
def fit_text_in_width(
    text: str, max_chars: int, truncate_suffix: str = "..."
) -> str:
    """
    Truncate text to fit within a maximum character count.

    Note: This is character-based truncation, not pixel-based.
    For pixel-perfect truncation, use PIL's textbbox with an actual font.

    Args:
        text: Text to truncate
        max_chars: Maximum number of characters (not pixels)
        truncate_suffix: Suffix to add when truncating

    Returns:
        Truncated text with suffix if truncated, otherwise original text
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(truncate_suffix)] + truncate_suffix
```

Also search the codebase for any callers passing pixel widths by mistake:

```bash
grep -rn "fit_text_in_width" ~/Solar-Smart-Clock/solar_clock/
```

Fix any callers that were passing pixel values expecting character-count behavior.

**Step 2: Run tests**

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/ -v
```

Expected: all PASS.

**Step 3: Commit**

```bash
cd ~/Solar-Smart-Clock
git add solar_clock/views/layout_helpers.py
git commit -m "cleanup: rename max_width to max_chars in fit_text_in_width to clarify it is character-based"
```

---

## Summary of Changes

| Task | File(s) | Type |
|------|---------|------|
| 1 | `views/clock.py`, `views/solar.py`, `views/sunpath.py` | Bug fix |
| 2 | `main.py` | Bug fix |
| 3 | `main.py` | Bug fix |
| 4 | `views/base.py` | Bug fix |
| 5 | `data/weather.py` | Bug fix |
| 6 | `data/solar.py` | Performance |
| 7 | `data/lunar.py` | Performance |
| 8 | `views/weather.py` | Performance |
| 9 | `touch_handler.py` | Bug fix |
| 10 | `views/base.py` | Cleanup |
| 11 | `data/weather.py` | Bug fix |
| 12 | `views/weather.py` | Cleanup |
| 13 | `config.py` | Cleanup |
| 14 | `views/layout_helpers.py` | Cleanup |

Run the full test suite after all tasks:

```bash
cd ~/Solar-Smart-Clock && ./venv/bin/pytest tests/ -v
```

Then deploy to clock.local:

```bash
rsync -av ~/Solar-Smart-Clock/ pi@clock.local:~/Solar-Smart-Clock/
ssh pi@clock.local "sudo systemctl restart solar-clock && sudo systemctl status solar-clock"
```
