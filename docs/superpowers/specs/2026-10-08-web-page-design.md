# Solar Clock Web Page — Design

**Date:** 2026-10-08
**Status:** Approved in conversation; awaiting written-spec review

## Goal

Make the Solar Clock's nine views available as a web page that can be glanced at
from a phone or laptop on the home network, without changing how the physical
clock (TFT on `clock.local`) works or looks.

## Agreed requirements

| Topic | Decision |
|---|---|
| Purpose | Glance from phone/laptop at home |
| Reach | Home network only. No public or remote access |
| Look | Native web layout (HTML/SVG drawn in the browser), adapts to phone portrait, crisp. Looks *similar* to the TFT, not pixel-identical |
| Scope | All 9 views, in two phases |
| Theme | Match the clock: same day/night switching and colours |
| Login | None. Matches today's port 8080, which answers without auth (login is configured in the secrets file but not active) |
| Hosting | Built into the existing clock process (approach A) |

### Assumptions confirmed by the user

- The page has its own navigation (swipe, arrows). It can never change what the
  physical clock shows.
- Time ticks every second in the browser; data refreshes about every 60 s.
- Phone portrait is the primary layout; laptop works too.
- Existing endpoints (`/screenshot`, `/next`, `/prev`, `/view`, `/theme`,
  `/health`) are unchanged.

### Non-goals

Add-to-home-screen icon / web manifest, offline mode, on-page settings,
controls for the physical clock, access from outside the home network,
pixel-identical rendering, a JS framework or build step.

## Context (as of 2026-10-08)

- `clock.local` is a Pi Zero 2 W (415 MB RAM). Service `solar-clock` runs from
  `~/solar-clock` (a clone of this repo) with `-v`.
- The HTTP server (`http_server.py`) is a single-threaded `HTTPServer` on
  `0.0.0.0:8080` with a 10 req/s token-bucket rate limiter.
- Views draw with Pillow at fixed 480×320 coordinates and get their data from
  `SolarProvider`, `LunarProvider` and `WeatherProvider` method calls.
- `LunarProvider` mutates a shared `ephem.Observer` (`self._observer.date = …`)
  inside `get_moon_times`, and `SolarProvider` rebuilds its `_sun_times_cache`
  dict on every miss. Neither is safe to call from two threads at once.
- `WeatherProvider` fetches on demand when its cache is stale. Two threads
  could both start a fetch.
- Baseline test suite: 262 collected, 259 passed, 3 skipped.
- CI: GitHub Actions, Python 3.9–3.12, black/flake8/mypy. New Python code must
  stay 3.9-compatible.

## Architecture

```
solar-clock.service (one process, as today)
├─ main loop ─► 9 views ─► TFT                    UNCHANGED
│    uses shared solar, lunar, weather providers
└─ HTTP server :8080 (existing thread)
     /screenshot /next /prev /view /theme /health   UNCHANGED
     NEW  /                → index.html
     NEW  /<static path>   → files under solar_clock/web/
     NEW  /api/now         → JSON for all views (polled every 60 s)
     NEW  /api/charts      → chart JSON (phase 2; fetched on load + hourly)
          uses: its OWN SolarProvider + LunarProvider (same config),
                the SHARED WeatherProvider,
                its OWN ThemeManager instance (not the singleton)
```

### Isolation rules

1. **Separate solar/lunar instances.** The web data service constructs its own
   `SolarProvider` and `LunarProvider` from the same `config.location`. They are
   pure calculations, so the numbers are identical, and the TFT's instances are never
   touched from the HTTP thread.
2. **Shared weather, guarded fetch.** `WeatherProvider` gains a non-blocking
   fetch lock. A caller that finds a fetch already in progress returns the
   cached value immediately instead of fetching again. The TFT never waits on a
   web-triggered fetch, and the API is never called twice for the same refresh.
3. **Theme read-only.** The web service reads the main `ThemeManager.mode`
   (a property read) and computes day/night with its own `ThemeManager`
   instance built on its own `SolarProvider`, syncing the mode only when it
   changes (to avoid `set_mode` log spam). It never calls `set_mode` on the
   main manager and never calls `ThemeManager.initialize`.
4. **Read-only endpoints.** New routes never touch `ViewManager` or change any
   clock state.
5. **Single-threaded web service.** The web service's own providers are only
   safe because `HTTPServer` handles one request at a time. The server is not
   switched to `ThreadingHTTPServer`. A comment in `web_api.py` records this.
6. **Untouched files:** everything in `solar_clock/views/`, `display.py`,
   `touch_handler.py`, and the main-loop body in `main.py`.

### Files

| File | Change |
|---|---|
| `solar_clock/web_api.py` | **New.** `WebDataService`: owns web solar/lunar/theme instances, builds `/api/now` and `/api/charts` dicts |
| `solar_clock/web/index.html`, `style.css`, `js/app.js`, `js/format.js`, `js/views/*.js`, `js/svg.js` (phase 2) | **New.** The page |
| `solar_clock/http_server.py` | Add routes: `/`, static allowlist, `/api/now`, `/api/charts`; static files exempt from rate limiting |
| `solar_clock/main.py` | Construct `WebDataService` in `SolarClock.__init__` (guarded) and hand it to `create_server` |
| `solar_clock/data/weather.py` | Non-blocking fetch lock around `_fetch_weather` / `_fetch_air_quality` |
| `setup.py` | `package_data` so `solar_clock/web/**` ships with an installed package |
| `tools/web_preview.py` | **New.** Dev-only: runs the HTTP server + `WebDataService` without a display, for building on homelab |
| `tests/test_web_api.py`, additions to `tests/test_http_server.py`, `tests/test_weather.py` | **New tests** |
| `tests/web/*.test.mjs` | **New.** JS tests run with `node --test` |
| `.github/workflows/test.yml` | Add a `node --test tests/web/` step |
| `README.md`, `CLAUDE.md` | Document the page URL and new endpoints |

## Data API

The server sends raw values; the browser formats them to match the TFT's
strftime patterns (e.g. `%-I:%M %p` → `6:42 AM`, `11h 23m`, `Feels 54°`).
Datetimes are ISO 8601 strings with offset in the configured timezone; dates
are `YYYY-MM-DD`.

### `GET /api/now` (phase 1, ~3 KB)

```jsonc
{
  "generated_at": "2026-10-08T07:12:00-04:00",
  "location": { "name": "…", "timezone": "America/New_York" },
  "units": "imperial",
  "theme": {
    "mode": "auto", "active": "night",
    "palettes": { "day": { /* all Theme fields */ }, "night": { … } },
    "colors": { /* fixed named colours from views/colors.py */ }
  },
  "sun": {
    "times": { "dawn", "sunrise", "noon", "sunset", "dusk" },
    "golden_hour": { "morning": { "start", "end" }, "evening": { "start", "end" } },
    "position": { "elevation": 12.4, "azimuth": 118.0 },
    "day_length_hours": 11.38,
    "day_length_change_min": -2.1,
    "next_event": { "name": "Sunset", "at": "…" }
  },
  "weather": {
    "current": { "temperature", "feels_like", "humidity", "description",
                 "wind_speed", "wind_direction" },
    "forecast": [ { "date", "high_temp", "low_temp", "rain_chance" } ]  // 3 days
  },
  "air_quality": { "aqi", "category", "pm25", "pm10", "o3", "no2", "so2", "co",
                   "updated_at" },
  "moon": {
    "phase": { "phase", "illumination", "phase_name", "next_new", "next_full",
               "days_to_new", "days_to_full" },
    "times": { "moonrise", "moonset" }
  }
}
```

Each top-level section (`theme`, `sun`, `weather`, `air_quality`, `moon`) is
built independently; any section may be `null`.

### `GET /api/charts` (phase 2)

Computed with the web service's own providers and cached in memory per local
date (recomputed once a day).

- `sun_path`: today's solar elevation sampled every 30 minutes (same as
  `SunPathView._draw_sun_curve`).
- `day_length`: day length sampled every 3 days across the year (same as
  `DayLengthView`), solstice/equinox dates, shortest and longest day lengths.
- `analemma`: `LunarProvider.get_analemma_data()` points plus current
  equation of time.

The live sun-position marker comes from `/api/now`.

### Computed in the browser

The clock time and date (in the configured timezone via `Intl.DateTimeFormat`),
the analog clock hands, "% of day", the next-event countdown, and the
time-of-day header colour (same thresholds as `BaseView.get_time_header_color`,
using sun times from `/api/now`).

## The page

- Each TFT view becomes one screen with the same header bar, title and header
  colour, rounded panels, accent colours and nav dots. Blocks that sit side by
  side on the 480×320 TFT stack vertically on a phone in portrait and flow
  side by side on wider screens.
- Navigation: swipe left/right, ‹ › buttons, keyboard ←/→. Opens on Clock.
  The current view is kept in the URL hash (e.g. `#moon`).
- Each view module exports a pure `render(data, now) → string` (HTML or SVG).
  `app.js` re-renders the current view every second from the last data and
  polls `/api/now` every 60 s.
- Theme colours are applied as CSS custom properties from
  `theme.palettes[theme.active]`.
- System sans-serif font (no web font download).
- No external network requests: everything is served by the clock.
- About 14 small static files on load; static routes are exempt from the
  rate limiter (API routes stay limited).

## Error handling

**Principle: no web-side failure may stop or change the clock.**

### Server

- `WebDataService` construction failure (e.g. missing `web/` dir) is logged
  and the clock runs without it; `/` and `/api/*` return 503.
- Each `/api/now` section is built in its own `try/except Exception`. The
  exception is logged and the section becomes `null`; the response is still
  200.
- No API key means `weather` and `air_quality` are `null`. A failed fetch
  keeps the last good data and uses the existing 60 s `RETRY_BACKOFF`.
- Static files are served only from an allowlist built at startup by walking
  `solar_clock/web/`. Unknown paths, including traversal attempts such as
  `/../config.json` or encoded variants, get 404.
- `Content-Type` is set by extension and `Cache-Control: no-cache` is set on
  static files, so a deploy is picked up on the next load.

### Browser

- **Fetch fails:** keep the last data on screen, keep ticking, and show the
  banner *"Can't reach clock · last update 7:12 AM"*. Retry every 60 s and
  clear the banner on success.
- **Never loaded:** show *"Connecting to clock…"*.
- **Section is `null`:** the view shows the same message the TFT shows in that
  case.
- **A view's `render` throws:** that view shows *"Couldn't draw this view"*,
  the error is logged to the console, and navigation and the other views keep
  working.
- **Countdowns:** clamp at zero; the next poll moves on to the next event.
- **API strings:** all strings from the API are HTML-escaped before insertion.

## Testing and verification

### Python (pytest, existing mock-based style)

- `WebDataService`:
  - builds JSON-serialisable output from fake providers;
  - a section is `null` when its provider is missing or raises;
  - datetimes carry the configured timezone;
  - palettes match the `Theme` dataclass fields;
  - the main `ThemeManager` mode is followed but never set;
  - `/api/charts` is cached per date.
- HTTP:
  - `/` and static files are served with the right content types;
  - traversal attempts get 404;
  - `/api/now` returns 200 JSON, or 503 when the service is absent;
  - static routes bypass the rate limiter and API routes do not;
  - existing endpoint tests are unchanged.
- Weather lock: two threads with an expired cache produce exactly one fetch,
  and the losing caller returns the cached value without blocking.
- **All 262 existing tests still collect, with 259 passing and 3 skipped. No
  existing test is edited.**

### JavaScript (`node --test`, no npm dependencies)

- `format.js`: outputs match the TFT strftime patterns; durations; countdown
  clamping.
- Every view `render()` with full data, with each section `null`, and with
  hostile strings (escaping).

### Proof the TFT is unchanged (end of each phase)

1. `git diff main -- solar_clock/views solar_clock/display.py solar_clock/touch_handler.py`
   is empty, and the main-loop body in `main.py` is unchanged.
2. Pixel parity: render all 9 views at the base commit and at the branch head
   with frozen time and identical stub providers; every image must be
   identical. This is a one-off script, not committed, because font
   differences between machines would make it flaky in CI.
3. On `clock.local` after deploy:
   - the service is active and the journal shows no new errors;
   - `/screenshot` of the current view matches the pre-deploy capture
     (allowing for time);
   - process RSS is recorded before deploy and about 1 h after with the page
     open;
   - Peter confirms one physical swipe still works.

## Delivery

| Phase | Contents | Done when |
|---|---|---|
| **1** | `WebDataService` + `/api/now`, static serving, weather fetch lock, page shell (nav, swipe, theme, banner), views: Clock, Weather, Air Quality, Solar Details, Moon, `tools/web_preview.py`, docs | Python + JS tests green, TFT proof passes, deployed to clock.local, Peter has used it on his phone |
| **2** | `/api/charts`, `svg.js`, views: Sun Path, Day Length, Analemma, Analog Clock | Same checks |

- Each phase is built on a local branch (`web-page-phase1`, `web-page-phase2`)
  and merged to `main` after verification. The repo does not use PRs.
- Pushing to GitHub and deploying to `clock.local` happen only on Peter's
  go-ahead.
- Deploy: `cd ~/solar-clock && git pull && sudo systemctl restart solar-clock`,
  then the on-device checks above.
- The page is at `http://clock.local:8080/`.
