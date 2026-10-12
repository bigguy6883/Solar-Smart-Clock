# Solar Clock Web Page, Phase 2: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the four remaining views (Sun Path, Day Length, Analemma and Analog Clock) to the web page at `http://clock.local:8080/`, so it shows all nine of the clock's views, while the physical TFT clock keeps working and looking exactly as it does now.

**Architecture:** The clock's web data service gains one read-only endpoint, `/api/charts`, which returns the three curves the chart views need (today's sun elevation, the year's day lengths, the analemma). It works them out once per day and keeps the answer in memory. The page fetches the charts once it has heard from the clock, and again only when the clock's date changes. Each new view is a plain JavaScript module that draws inline SVG from that data, in the same pattern as the five phase 1 views. The Analog Clock needs no new data.

**Tech Stack:** Python 3.9+ (stdlib `http.server`, astral, ephem, all already installed), vanilla ES modules, HTML/CSS/inline SVG, pytest, Node's built-in test runner (`node --test`; homelab has Node 24).

**Spec:** `docs/superpowers/specs/2026-10-08-web-page-design.md` (approved 2026-10-08). Its "`GET /api/charts` (phase 2)" section and Delivery row 2 are what this plan builds. Read it before starting; this plan argues from it.

**Phase 1** is live on clock.local at commit `f67a8ed`: plan `docs/superpowers/plans/2026-10-08-web-page-phase1.md`. This plan reuses its helpers, test style and deploy steps.

## For Peter: what to decide before this is built

Nothing below blocks the build. Each item has a default the plan follows unless you say otherwise.

1. **The Analemma's "Sun early" and "Sun late" labels are on the wrong sides on the TFT.** The clock plots a fast sun to the right, but prints "Sun early" on the left. Today's dot (13.5 minutes early) sits beside "Sun late", while the box next to it says "early". **Default: the page copies the TFT as it is**, because this project's rule is that the page mirrors the clock and the clock is not changed. Swapping the two labels is a two-word change on each side; say so and it becomes a small separate commit that changes the TFT too.
2. **Other TFT habits the page copies on purpose** (no decision needed, listed so they aren't mistaken for page bugs):
   - Sun Path: the chart's scale runs from 40° down to -90°, so a summer sun climbs above the top line. On the TFT that part of the curve is drawn over the header; the page makes the picture taller instead, so nothing is hidden.
   - Sun Path: the night part of the curve is dark blue, which is faint on the black night theme.
   - Day Length: after the winter solstice (22-31 December) the "Next" box is empty.
   - Analemma: the "Sun path" box always ends in "S", and reads "low" with a negative angle at night.
3. **Two small departures from the spec**, both simpler than what it says:
   - The spec has the page fetch the charts "on load + hourly". The clock only recalculates them once a day, so hourly fetches would return the same answer 23 times. The page instead fetches them on load and whenever the clock's date changes.
   - Phase 1's rule "no existing test is edited" still holds for every TFT test. Three of phase 1's own web-page tests are extended, because the list of views grows (Tasks 4-6 say exactly where).

## How this plan was checked

Every code block below was run before the plan was written (2026-10-11), in a scratch copy of the repo at commit `f67a8ed` with all phase 2 changes applied. The tasks were then replayed one at a time on a second clean copy, tests first, to record what each step should print.

- **Python:** 322 passed, 3 skipped (308 existing + 14 new tests).
- **JavaScript:** 85 passed under Node 24 (44 existing + 41 new), and again with the machine's timezone set to `Asia/Tokyo`, `UTC` and `Pacific/Kiritimati`.
- **Linters:** `black --check`, `flake8` and `mypy` (project flags) were clean, and so was the repo's whole pre-commit set (which pins black 24.1.1). `web_api.py` was clean under `mypy --strict`; `web_api.py` and the three edited test files were clean under `ruff 0.16.10 --target-version py39`; `http_server.py` has the same 5 ruff findings before and after.
- **Tests have teeth:** 9 deliberate one-line breaks (for example "never refetch the charts", "rename a field in the API", "drop the chart's rotation", "retry a failed chart on every request") each made at least one test fail.
- **TFT pixel parity:** 18 of 18 renders identical (9 views x day and night), and `git diff` over the TFT's files is empty.
- **Packaging:** a wheel built from `setup.py` contains all 24 page files.
- **Preview server:** `/`, the new files and `/api/charts` answer 200; `/api/charts` is 6.3 KB and took 0.07 s the first time and 0.002 s after that on homelab (a Pi 4; expect a few times longer, once a day, on the clock's Pi Zero 2 W).
- **Layout:** the new views were screenshotted from static snapshots: all four at 390 px wide (phone portrait), and a sample of them at 360 px, at 844 x 390 (phone landscape) and at 900 px (laptop), across the day and night themes. Three things were fixed as a result: the Sun Path chart no longer reserves empty space for a summer sun in autumn, "15h 05m" no longer wraps in the Day Length box, and the Analemma stacks its diagram above its boxes on a phone (the spec's rule for side-by-side blocks) instead of squeezing both.

Three things the checks surfaced, so you aren't surprised:

- **A failed chart must not be recalculated on every request.** The first draft kept nothing in memory when a chart failed, so on a clock where one chart always fails (no `ephem`, say) every `/api/charts` request would have redone a full year of sun calculations, and anyone on the network could have kept the Pi Zero busy with it. A security check on the scratch commit caught this. Task 1 now always keeps the answer and retries a failed chart at most once every 5 minutes, with a test.

- **Expected console noise.** The `app.js` tests print `Could not reach the clock Error: offline`, `Could not load the charts Error: HTTP 503` and `The clock view failed to draw TypeError...`. Those lines come from tests that cause the failures on purpose.
- **The contract test passes before Task 6's code.** In Task 6 the tightened contract test is green as soon as it is written, because the views (Tasks 4-5) and the data (Task 1) already agree. It is there to keep them agreeing.

## Global Constraints

- Run everything from the repo root `~/Solar-Smart-Clock` on branch `web-page-phase2`. That branch already exists (cut from `main` at `f67a8ed`) and holds this plan.
- **TFT untouched:** do not modify anything in `solar_clock/views/`, `solar_clock/data/`, `solar_clock/display.py`, `solar_clock/touch_handler.py` or `solar_clock/main.py`.
- **TFT tests untouched.** No test of the TFT or its providers is edited. Phase 1's web-page tests are edited only where a task says so. Baseline: Python 308 passed, 3 skipped; JavaScript 44 passed.
- **Read-only endpoints:** new routes never call `ViewManager` and never call `set_mode` on the clock's `ThemeManager` or `ThemeManager.initialize`.
- **Single-threaded server:** `HTTPServer` stays single-threaded. Do not switch to `ThreadingHTTPServer`; `web_api.py` relies on it.
- **Python 3.9 compatible** (CI runs 3.9-3.12):
  - `web_api.py` already has `from __future__ import annotations`, so `X | None` is fine in annotations.
  - Runtime expressions (type aliases, `isinstance`) must not use `X | Y`.
  - No `match` statements.
- **No new dependencies:** no Python packages, no npm packages, no JS framework, no build step, and no request from the page to anything but the clock.
- **Static files:** no new file types. The new `.js` files are picked up by the allowlist that `StaticSite` builds at startup, and by `setup.py`'s existing `web/js/*.js` and `web/js/views/*.js` patterns.
- **Formatting:** page text matches the TFT's strftime patterns, shown in the configured timezone (`config.location.timezone`), not the viewer's. Numbers round like Python's `format()` (use `fixed()` from `format.js`).
- **Messages:** when a data section is `null`, the view shows what the TFT shows in that case.
- **Escaping:** every string from the API goes through `escapeHtml()`. Every number from the API that ends up in SVG goes through `n()` from `svg.js` or `fixed()`, never straight into the markup.
- **Lint gates for every commit that touches Python:**
  - `./venv/bin/black --check solar_clock tests`
  - `./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503`
  - `./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary`
- **Extra gates** (Peter's global rule): `web_api.py` stays clean under `mypy --strict` and `ruff check --target-version py39`; `http_server.py` gains no new ruff findings (it has 5 today). Set up ruff once, outside the repo, in your scratchpad: `python3 -m venv <scratchpad>/ruffenv && <scratchpad>/ruffenv/bin/pip install -q ruff==0.16.10`.
- **Privacy:** never commit `config.json`, coordinates, API keys or IP addresses.
- **Commits:** end every commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. If the commit hook reformats a file, re-stage it and commit again.
- **Gated actions:** pushing to GitHub and deploying to clock.local happen only after Peter says so (Task 8).

## Review Focus

These are the five failure modes most likely to bite someone using the page that ordinary per-function tests would miss. Each is pinned by a test in the task that owns the code:

1. **The real `/api/charts` drifts from the JavaScript's sample data** (a renamed or missing field): the chart views would draw empty frames or "undefined" on the phone while every JS test passes. Pinned by `tests/test_web_contract.py`, which feeds the real JSON through Node into every view and checks the curves were drawn (Task 6).
2. **The page stays open past midnight** (a tablet on a shelf, a pinned laptop tab): today's sun path and "today" dot must move on without a reload, and without fetching the charts on every poll. Pinned by `app.test.mjs` "the charts are fetched again only when the clock's date moves on" (Task 6) and `test_charts_are_worked_out_once_per_date` (Task 1).
3. **The charts request fails or hangs while the clock itself answers:** the other views and the chart views' text must keep working, with no "Can't reach clock" banner, and the charts must arrive on a later poll. Pinned by `app.test.mjs` "a failed charts request..." and "a chart view draws its frame..." (Task 6), and each view's "without the charts" test (Tasks 4-5).
4. **Late December, 1 January and leap years on the Day Length view:** the chart is turned so today is in the middle, which wraps around the year end. Pinned by `daylength.test.mjs` "year ends and leap years..." and "after the winter solstice..." (Task 4).
5. **Summer on the Sun Path view:** the TFT's scale stops at 40°, and the sun reaches about 73° in June. The curve and the sun's marker must stay visible. Pinned by `sunpath.test.mjs` "the picture grows upwards..." (Task 4).

A sixth, checked in Task 7 rather than by one test: **a viewer whose device is in another timezone** must see the clock's time of day on the Sun Path marker and the Analog Clock's hands. Each view has a test with the timezone set to Tokyo, and Task 7 runs the whole JavaScript suite with the machine itself set to three other timezones.

## File map

| File | Status | Responsibility |
|---|---|---|
| `solar_clock/web_api.py` | modify | `WebDataService.build_charts()`: the three curves, cached per date (Task 1) |
| `solar_clock/http_server.py` | modify | Route `/api/charts` (Task 2) |
| `solar_clock/web/js/format.js` | modify | Five date helpers the chart views need (Task 3) |
| `solar_clock/web/js/svg.js` | create | `n()`, `scale()`, `linePath()` for inline SVG (Task 3) |
| `solar_clock/web/js/views/sunpath.js`, `daylength.js` | create | Sun Path and Day Length views (Task 4) |
| `solar_clock/web/js/views/analemma.js`, `analogclock.js` | create | Analemma and Analog Clock views (Task 5) |
| `solar_clock/web/js/views/index.js` | modify | View list grows to nine, in TFT order (Tasks 4-5) |
| `solar_clock/web/style.css` | modify | Chart, analemma and analog clock styles (Tasks 4-5) |
| `solar_clock/web/js/app.js` | modify | Fetch `/api/charts`, hand it to the views (Task 6) |
| `tests/test_web_api.py`, `tests/test_http_server.py` | append | New tests only (Tasks 1-2) |
| `tests/test_web_contract.py` | modify | Feed the real charts to the views too (Task 6) |
| `tests/web/fixtures.mjs`, `format.test.mjs` | modify | Sample charts; tests for the new helpers (Task 3) |
| `tests/web/svg.test.mjs`, `sunpath.test.mjs`, `daylength.test.mjs`, `analemma.test.mjs`, `analogclock.test.mjs` | create | JS tests (Tasks 3-5) |
| `tests/web/views.test.mjs` | rewrite | Same four tests on nine views, plus one (Tasks 4-5) |
| `tests/web/dom-stub.mjs`, `app.test.mjs` | modify | The fake page answers `/api/charts`; five new shell tests (Task 6) |
| `README.md`, `CLAUDE.md` | modify | Document the new views and endpoint (Task 7) |

Not changed: `solar_clock/main.py` (the service is already built there), `tools/web_preview.py` (it serves whatever the service offers), `setup.py`, `index.html`, the icons and the CI workflow.

---

### Task 1: Chart data (`WebDataService.build_charts`)

The three curves, built from the web service's own `SolarProvider` and `LunarProvider` with the same sampling the TFT views use, and kept in memory for the rest of the day.

**Files:**
- Modify: `solar_clock/web_api.py`
- Test: `tests/test_web_api.py` (one import grows, tests are appended; no existing test changes)

**Interfaces:**
- Consumes: `WebDataService.__init__`, `_section()`, `self._solar`, `self._lunar`, `self._tz` from phase 1.
- Produces:
  - `WebDataService.build_charts() -> dict[str, Any]`, shaped as below. Each of the three charts is built on its own; one that raises is logged and sent as `None`.
  - `WebDataService._today() -> datetime.date`: today's date in the clock's timezone. Tests replace it to pin the calendar.
  - Module constants `SUN_PATH_STEP_MINUTES = 30`, `DAY_LENGTH_STEP_DAYS = 3` and `CHART_RETRY_SECONDS = 300.0`.

```jsonc
{
  "date": "2026-10-08",                    // the clock's local date these were built for
  "sun_path": {
    "step_minutes": 30,
    "elevations": [-53.81, -55.03, ...]    // 48 values from local midnight; null where unknown
  },
  "day_length": {
    "year": 2026,
    "points": [[0, 9.314], [3, 9.355], ...], // [days since 1 Jan, hours]; days without a sunrise or sunset are left out
    "shortest": { "date": "2026-12-21", "hours": 9.245 },   // winter solstice; hours may be null
    "longest":  { "date": "2026-06-21", "hours": 15.087 },  // summer solstice; hours may be null
    "events": [ { "name": "Vernal", "date": "2026-03-20" }, { "name": "Summer", ... },
                { "name": "Autumn", ... }, { "name": "Winter", ... } ]
  },
  "analemma": {                            // null when ephem is not installed
    "points": [ { "date": "2026-01-01", "elevation": 26.33, "equation_of_time": -3.57 }, ... ],  // weekly
    "equation_of_time": 12.73              // today's, in minutes; positive means the sun is early
  }
}
```

Rules this task follows:
- **Sampling copies the TFT:** every 30 minutes of the local day (`SunPathView._draw_sun_curve`), every 3rd day of the year (`DayLengthView._render_yearly_curve`), and `LunarProvider.get_analemma_data()` as it is (`AnalemmaView`).
- **Cached per date:** the second call on the same local date returns the very same dict without recalculating.
- **A missing chart is retried, but not on every request:** if any chart came out `None`, the answer is still kept and served as it is for `CHART_RETRY_SECONDS` (5 minutes), then everything is worked out again. A one-off failure doesn't stick for the rest of the day, and a chart that always fails can't be used to keep the clock's processor busy.
- **The clock's own day:** samples start at local midnight in `config.location.timezone`, not UTC and not the system timezone.

- [ ] **Step 1: Write the failing tests.** In `tests/test_web_api.py`, change the import of `solar_clock.web_api` to:

```python
from solar_clock.web_api import CHART_RETRY_SECONDS, WebDataService, hex_color, iso
```

Then append this to the end of the file:

```python
# --- GET /api/charts -------------------------------------------------------

OCT_8 = datetime.date(2026, 10, 8)


@pytest.fixture
def charts_service(service):
    """The service with its calendar pinned to Thursday 8 Oct 2026."""
    service._today = lambda: OCT_8
    return service


def test_build_charts_is_json_with_every_section(charts_service):
    data = json.loads(json.dumps(charts_service.build_charts()))
    assert set(data) == {"date", "sun_path", "day_length", "analemma"}
    assert data["date"] == "2026-10-08"

    sun_path = data["sun_path"]
    assert sun_path["step_minutes"] == 30
    assert len(sun_path["elevations"]) == 48

    day_length = data["day_length"]
    assert day_length["year"] == 2026
    assert [day for day, _ in day_length["points"]] == list(range(0, 365, 3))
    assert all(9 < hours < 15.5 for _, hours in day_length["points"])
    assert day_length["shortest"]["date"] == "2026-12-21"
    assert day_length["longest"]["date"] == "2026-06-21"
    assert day_length["shortest"]["hours"] < 9.5
    assert day_length["longest"]["hours"] > 15
    assert [event["name"] for event in day_length["events"]] == [
        "Vernal",
        "Summer",
        "Autumn",
        "Winter",
    ]
    assert day_length["events"][2]["date"] == "2026-09-23"

    analemma = data["analemma"]
    assert len(analemma["points"]) == 53
    assert set(analemma["points"][0]) == {"date", "elevation", "equation_of_time"}
    assert analemma["points"][0]["date"] == "2026-01-01"
    assert 12 < analemma["equation_of_time"] < 13  # early October: sun ~12.5 min early


def test_sun_path_is_sampled_on_the_clocks_own_day(charts_service):
    elevations = charts_service.build_charts()["sun_path"]["elevations"]
    # New York, 8 Oct: dark at local midnight, highest near 12:45 PM local.
    assert elevations[0] < -40
    assert elevations.index(max(elevations)) in (25, 26)
    assert 40 < max(elevations) < 45


def test_sun_path_copes_with_a_23_hour_day(charts_service):
    charts_service._today = lambda: datetime.date(2026, 3, 8)  # clocks go forward
    elevations = charts_service.build_charts()["sun_path"]["elevations"]
    assert len(elevations) == 48
    assert all(isinstance(value, float) for value in elevations)


def test_charts_are_worked_out_once_per_date(charts_service):
    first = charts_service.build_charts()
    charts_service._solar.get_day_length = MagicMock(
        wraps=charts_service._solar.get_day_length
    )
    assert charts_service.build_charts() is first
    charts_service._solar.get_day_length.assert_not_called()

    charts_service._today = lambda: datetime.date(2026, 10, 9)
    second = charts_service.build_charts()
    assert second["date"] == "2026-10-09"
    assert second is not first
    charts_service._solar.get_day_length.assert_called()


def test_a_failing_chart_is_null_and_logged(charts_service, caplog):
    charts_service._solar.get_solar_position = MagicMock(
        side_effect=RuntimeError("astral broke")
    )
    with caplog.at_level(logging.ERROR, logger="solar_clock.web_api"):
        data = charts_service.build_charts()
    assert data["sun_path"] is None
    assert data["day_length"] is not None
    assert data["analemma"] is not None
    assert "'sun_path' failed" in caplog.text


def test_a_failed_chart_is_retried_later_but_not_on_every_request(
    charts_service, monkeypatch
):
    clock = [1000.0]
    monkeypatch.setattr("solar_clock.web_api.time.monotonic", lambda: clock[0])
    working = charts_service._solar.get_solar_position
    charts_service._solar.get_solar_position = MagicMock(
        side_effect=RuntimeError("astral broke")
    )
    failed = charts_service.build_charts()
    assert failed["sun_path"] is None

    # Asking again at once costs nothing: no chart is worked out a second time.
    charts_service._solar.get_solar_position = working
    charts_service._solar.get_day_length = MagicMock(
        wraps=charts_service._solar.get_day_length
    )
    clock[0] += CHART_RETRY_SECONDS - 1
    assert charts_service.build_charts() is failed
    charts_service._solar.get_day_length.assert_not_called()

    clock[0] += 1
    assert charts_service.build_charts()["sun_path"] is not None


def test_analemma_is_null_when_ephem_is_unavailable(charts_service, monkeypatch):
    monkeypatch.setattr("solar_clock.data.lunar.EPHEM_AVAILABLE", False)
    data = json.loads(json.dumps(charts_service.build_charts()))
    assert data["analemma"] is None
    # The day length chart still gets its dates, from the provider's fallback.
    assert data["day_length"]["shortest"]["date"] == "2026-12-21"


def test_day_length_skips_days_the_sun_does_not_rise_or_set(sample_config):
    sample_config.location.latitude = 78.2  # Svalbard: polar night and midnight sun
    service = WebDataService(sample_config, weather=None, theme_mode=lambda: "auto")
    service._today = lambda: OCT_8
    day_length = json.loads(json.dumps(service.build_charts()))["day_length"]
    assert 0 < len(day_length["points"]) < 122
    assert all(isinstance(hours, float) for _, hours in day_length["points"])
    assert day_length["shortest"]["hours"] is None
    assert day_length["longest"]["hours"] is None
```

- [ ] **Step 2: Run them and watch them fail**

Run: `./venv/bin/pytest tests/test_web_api.py -q`
Expected: `1 error`, during collection: `ImportError: cannot import name 'CHART_RETRY_SECONDS' from 'solar_clock.web_api'`.

- [ ] **Step 3: Implement.** Apply this change to `solar_clock/web_api.py`:

````diff
--- a/solar_clock/web_api.py
+++ b/solar_clock/web_api.py
@@ -1,4 +1,4 @@
-"""Data for the Solar Clock web page: the JSON behind GET /api/now.
+"""Data for the Solar Clock web page: the JSON behind GET /api/now and /api/charts.

 Threading: the page is served by the single-threaded HTTPServer in
 http_server.py, so one request runs at a time. That is what makes this
@@ -14,6 +14,7 @@ from __future__ import annotations
 import dataclasses
 import datetime
 import logging
+import time
 from collections.abc import Callable
 from typing import Any, Optional
 from zoneinfo import ZoneInfo
@@ -29,6 +30,13 @@ logger = logging.getLogger(__name__)
 # A runtime alias, so it uses Optional: Python 3.9 can't evaluate X | None.
 Section = Optional[dict[str, Any]]

+# The same sampling as the TFT's chart views.
+SUN_PATH_STEP_MINUTES = 30
+DAY_LENGTH_STEP_DAYS = 3
+
+# How long a chart that could not be built is sent as null before trying again.
+CHART_RETRY_SECONDS = 300.0
+

 def hex_color(rgb: tuple[int, int, int]) -> str:
     """'#rrggbb' for an (r, g, b) tuple."""
@@ -94,6 +102,8 @@ class WebDataService:
             latitude=loc.latitude, longitude=loc.longitude, timezone=loc.timezone
         )
         self._theme = ThemeManager(self._solar)  # not the singleton
+        self._charts: tuple[datetime.date, dict[str, Any]] | None = None
+        self._charts_retry_at = 0.0  # time.monotonic() value; only used after a failure

     def build_now(self) -> dict[str, Any]:
         """Everything the phase 1 views need. A failing section becomes None."""
@@ -113,6 +123,35 @@ class WebDataService:
             "moon": self._section("moon", self._moon_section),
         }

+    def build_charts(self) -> dict[str, Any]:
+        """The curves behind the chart views. Worked out once per local date.
+
+        If a chart could not be built, the answer is still kept, so requests
+        can't make the clock redo the work each time, and it is worked out
+        again once CHART_RETRY_SECONDS have passed.
+        """
+        today = self._today()
+        if self._charts is not None and self._charts[0] == today:
+            charts = self._charts[1]
+            complete = all(value is not None for value in charts.values())
+            if complete or time.monotonic() < self._charts_retry_at:
+                return charts
+        charts = {
+            "date": today.isoformat(),
+            "sun_path": self._section("sun_path", lambda: self._sun_path(today)),
+            "day_length": self._section(
+                "day_length", lambda: self._day_length_chart(today)
+            ),
+            "analemma": self._section("analemma", lambda: self._analemma(today)),
+        }
+        self._charts = (today, charts)
+        self._charts_retry_at = time.monotonic() + CHART_RETRY_SECONDS
+        return charts
+
+    def _today(self) -> datetime.date:
+        """Today's date where the clock is."""
+        return datetime.datetime.now(self._tz).date()
+
     @staticmethod
     def _section(name: str, build: Callable[[], Section]) -> Section:
         try:
@@ -219,3 +258,60 @@ class WebDataService:
                 }
             ),
         }
+
+    def _sun_path(self, today: datetime.date) -> Section:
+        """Sun elevation every 30 minutes of the day (SunPathView._draw_sun_curve)."""
+        midnight = datetime.datetime.combine(today, datetime.time(), tzinfo=self._tz)
+        elevations: list[float | None] = []
+        for minutes in range(0, 24 * 60, SUN_PATH_STEP_MINUTES):
+            position = self._solar.get_solar_position(
+                midnight + datetime.timedelta(minutes=minutes)
+            )
+            elevations.append(
+                None if position is None else round(position.elevation, 2)
+            )
+        return {"step_minutes": SUN_PATH_STEP_MINUTES, "elevations": elevations}
+
+    def _day_length_chart(self, today: datetime.date) -> Section:
+        """Day length through the year, and its turning points (DayLengthView)."""
+        new_year = datetime.date(today.year, 1, 1)
+        points = []
+        for day in range(0, 365, DAY_LENGTH_STEP_DAYS):
+            hours = self._solar.get_day_length(new_year + datetime.timedelta(days=day))
+            if hours is not None:
+                points.append([day, round(hours, 3)])
+        dates = self._lunar.get_solstice_equinox(today.year)
+        return {
+            "year": today.year,
+            "points": points,
+            "shortest": self._day_on(dates.winter_solstice),
+            "longest": self._day_on(dates.summer_solstice),
+            "events": [
+                {"name": name, "date": date.isoformat()}
+                for name, date in (
+                    ("Vernal", dates.spring_equinox),
+                    ("Summer", dates.summer_solstice),
+                    ("Autumn", dates.fall_equinox),
+                    ("Winter", dates.winter_solstice),
+                )
+            ],
+        }
+
+    def _day_on(self, date: datetime.date) -> dict[str, Any]:
+        return {"date": date.isoformat(), "hours": self._solar.get_day_length(date)}
+
+    def _analemma(self, today: datetime.date) -> Section:
+        """The year's noon sun positions and today's equation of time (AnalemmaView)."""
+        if not self._lunar.available:
+            return None
+        return {
+            "points": [
+                {
+                    "date": point.date.isoformat(),
+                    "elevation": round(point.elevation, 2),
+                    "equation_of_time": round(point.equation_of_time, 2),
+                }
+                for point in self._lunar.get_analemma_data()
+            ],
+            "equation_of_time": self._lunar.get_equation_of_time(today),
+        }
````

- [ ] **Step 4: Run the tests**

Run: `./venv/bin/pytest tests/test_web_api.py -q` and then `./venv/bin/pytest -q`
Expected: `21 passed`, then `316 passed, 3 skipped`.

- [ ] **Step 5: Lint.** Run:

```bash
./venv/bin/black --check solar_clock tests
./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503
./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
```

Expected: black reports nothing to change, flake8 prints nothing, and mypy prints only its two existing notes about `font_manager.py`.

Then the extra gates for this module:

```bash
./venv/bin/mypy --strict --ignore-missing-imports --follow-imports=silent solar_clock/web_api.py
<scratchpad>/ruffenv/bin/ruff check --no-cache --target-version py39 solar_clock/web_api.py tests/test_web_api.py
```

Expected: `Success: no issues found in 1 source file` and `All checks passed!`.

- [ ] **Step 6: Commit**

```bash
git add solar_clock/web_api.py tests/test_web_api.py
git commit -m "Add chart data for the web page's chart views" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The `/api/charts` route

**Files:**
- Modify: `solar_clock/http_server.py` (`_send_api_now` becomes `_send_api`; one route line)
- Test: `tests/test_http_server.py` (append one class; nothing existing changes)

**Interfaces:**
- Consumes: `WebDataService.build_charts()` from Task 1; `_request(path, request_headers=None)`, the module-level test helper already in `tests/test_http_server.py`, which returns `(status, headers, body)`.
- Produces: `GET /api/charts` answers 200 with the JSON from `build_charts()`, 503 when there is no web service, 500 (`{"error": "internal error"}`, no details) when building fails. Like `/api/now` it ignores a query string, counts against the rate limit, and touches nothing on the clock.

- [ ] **Step 1: Write the failing tests.** Append this class to the end of `tests/test_http_server.py`:

```python
class TestChartsRoute:
    """GET /api/charts: the curves behind the web page's chart views."""

    @pytest.fixture(autouse=True)
    def web_handler(self):
        ScreenshotHandler.clock_instance = MagicMock()
        ScreenshotHandler.rate_limiter = None
        ScreenshotHandler.auth_credentials = None
        ScreenshotHandler.static_site = None
        ScreenshotHandler.web_service = MagicMock()
        ScreenshotHandler.web_service.build_charts.return_value = {"date": "2026-10-08"}
        yield
        ScreenshotHandler.web_service = None

    def test_api_charts_returns_json(self):
        status, headers, body = _request("/api/charts")
        assert status == 200
        assert headers["Content-Type"] == "application/json"
        assert json.loads(body) == {"date": "2026-10-08"}

    def test_api_charts_ignores_a_query_string(self):
        assert _request("/api/charts?v=2")[0] == 200

    def test_api_charts_reads_nothing_else(self):
        _request("/api/charts")
        ScreenshotHandler.web_service.build_now.assert_not_called()
        assert ScreenshotHandler.clock_instance.mock_calls == []

    def test_api_charts_is_503_without_the_service(self):
        ScreenshotHandler.web_service = None
        assert _request("/api/charts")[0] == 503

    def test_api_charts_is_500_when_building_fails(self):
        ScreenshotHandler.web_service.build_charts.side_effect = RuntimeError("boom")
        status, _, body = _request("/api/charts")
        assert status == 500
        assert b"boom" not in body

    def test_api_charts_is_rate_limited(self):
        ScreenshotHandler.rate_limiter = RateLimiter(rate_per_second=1)
        assert _request("/api/charts")[0] == 200
        assert _request("/api/charts")[0] == 429
```

- [ ] **Step 2: Run them and watch them fail**

Run: `./venv/bin/pytest tests/test_http_server.py -q`
Expected: `5 failed, 46 passed`. The route doesn't exist yet, so the requests get 404. (`test_api_charts_reads_nothing_else` passes already, and must keep passing.)

- [ ] **Step 3: Implement.** Apply this change to `solar_clock/http_server.py`:

````diff
--- a/solar_clock/http_server.py
+++ b/solar_clock/http_server.py
@@ -133,15 +133,18 @@ class ScreenshotHandler(BaseHTTPRequestHandler):
         self.end_headers()
         self.wfile.write(body)

-    def _send_api_now(self) -> None:
+    def _send_api(self, route: str) -> None:
         """Send the web page's data. Read-only: never changes clock state."""
         if self.web_service is None:
             self._send_text(503, "Web page not available")
             return
         try:
-            data = self.web_service.build_now()
+            if route == "/api/charts":
+                data = self.web_service.build_charts()
+            else:
+                data = self.web_service.build_now()
         except Exception:
-            logger.exception("/api/now failed")
+            logger.exception(f"{route} failed")
             self._send_json(500, {"error": "internal error"})
             return
         self._send_json(200, data)
@@ -259,8 +262,8 @@ class ScreenshotHandler(BaseHTTPRequestHandler):
             # Only reached when the page's files failed to load at startup.
             self._send_text(503, "Web page not available")

-        elif route == "/api/now":
-            self._send_api_now()
+        elif route in ("/api/now", "/api/charts"):
+            self._send_api(route)

         else:
             self._send_text(404, "Not Found")
````

- [ ] **Step 4: Run the tests**

Run: `./venv/bin/pytest tests/test_http_server.py -q` and then `./venv/bin/pytest -q`
Expected: `51 passed`, then `322 passed, 3 skipped`.

- [ ] **Step 5: Lint.** Run:

```bash
./venv/bin/black --check solar_clock tests
./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503
./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
```

Expected: black reports nothing to change, flake8 prints nothing, and mypy prints only its two existing notes about `font_manager.py`.

Then check `http_server.py` gained no ruff findings:

```bash
<scratchpad>/ruffenv/bin/ruff check --no-cache --target-version py39 --output-format concise solar_clock/http_server.py | grep -c "^solar_clock"
```

Expected: `5`, the same as before this task.

- [ ] **Step 6: Commit**

```bash
git add solar_clock/http_server.py tests/test_http_server.py
git commit -m "Serve the chart data at /api/charts" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Page foundations: date helpers, SVG helpers and sample charts

**Files:**
- Modify: `solar_clock/web/js/format.js`, `tests/web/format.test.mjs`, `tests/web/fixtures.mjs`
- Create: `solar_clock/web/js/svg.js`, `tests/web/svg.test.mjs`

**Interfaces:**
- Consumes: `zoned(value, timeZone)`, `MONTHS`, `pad2` inside `format.js`; `sampleNow()`, `HOSTILE`, `NOW`, `TZ` from `fixtures.mjs`.
- Produces, in `format.js`:
  - `shortWeekdayDate(now, timeZone)` -> `"Thu Oct 08"` (the TFT's `%a %b %d`)
  - `weekdayDate(now, timeZone)` -> `"Thursday, October 08"` (`%A, %B %d`)
  - `isoDate(value, timeZone)` -> `"2026-10-08"`, the calendar day of an instant in that timezone
  - `daysBetween(from, to)` -> whole days between two `"YYYY-MM-DD"` strings; negative when `to` is earlier
  - `addDays(isoDay, days)` -> the `"YYYY-MM-DD"` that many days later (or earlier, when negative)
- Produces, in `svg.js`:
  - `n(value)` -> a number as SVG attribute text with one decimal at most; anything that isn't a number becomes `"NaN"`, never markup
  - `scale(d0, d1, r0, r1)` -> a function mapping `d0..d1` onto `r0..r1` in a straight line
  - `linePath(points)` -> path data through `[[x, y], ...]`, or `""` for fewer than two points
- Produces, in `fixtures.mjs`:
  - `sampleCharts()` -> a fresh `/api/charts` sample for 8 Oct 2026
  - `samplePage()` -> what `app.js` hands a view: `{ ...sampleNow(), charts: sampleCharts() }`

Date arithmetic is done on `"YYYY-MM-DD"` strings through `Date.UTC`, so it never depends on the viewer's timezone or on clock changes.

- [ ] **Step 1: Write the failing tests.** Apply this change to `tests/web/format.test.mjs` (the import list grows; three tests are added at the end):

````diff
--- a/tests/web/format.test.mjs
+++ b/tests/web/format.test.mjs
@@ -2,8 +2,9 @@ import { test } from "node:test";
 import assert from "node:assert/strict";

 import {
-  clockParts, compass8, countdownHM, dayFraction, dayLengthPadded, dayLengthText,
-  escapeHtml, fixed, longDate, shortDate, time12, time12Bare, weekdayShort, zoned,
+  addDays, clockParts, compass8, countdownHM, dayFraction, dayLengthPadded, dayLengthText,
+  daysBetween, escapeHtml, fixed, isoDate, longDate, shortDate, shortWeekdayDate, time12,
+  time12Bare, weekdayDate, weekdayShort, zoned,
 } from "../../solar_clock/web/js/format.js";
 import { NOW, TZ } from "./fixtures.mjs";

@@ -67,3 +68,27 @@ test("fixed() rounds like Python format()", () => {
 test("escapeHtml neutralises markup", () => {
   assert.equal(escapeHtml(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
 });
+
+test("the chart views' dates match the TFT's strftime patterns", () => {
+  assert.equal(shortWeekdayDate(NOW, TZ), "Thu Oct 08"); // %a %b %d
+  assert.equal(weekdayDate(NOW, TZ), "Thursday, October 08"); // %A, %B %d
+  assert.equal(shortWeekdayDate(NOW, "Asia/Tokyo"), "Fri Oct 09");
+});
+
+test("isoDate is the clock's calendar day, not the viewer's", () => {
+  const lateEvening = new Date("2026-10-08T23:30:00-04:00");
+  assert.equal(isoDate(lateEvening, TZ), "2026-10-08");
+  assert.equal(isoDate(lateEvening, "Asia/Tokyo"), "2026-10-09");
+  assert.equal(isoDate("2026-01-01T00:00:00-05:00", TZ), "2026-01-01");
+});
+
+test("day arithmetic crosses months, years, leap days and clock changes", () => {
+  assert.equal(daysBetween("2026-01-01", "2026-10-08"), 280);
+  assert.equal(daysBetween("2026-10-08", "2026-12-21"), 74);
+  assert.equal(daysBetween("2026-12-21", "2026-10-08"), -74);
+  assert.equal(daysBetween("2028-01-01", "2028-12-31"), 365); // leap year
+  assert.equal(daysBetween("2026-03-07", "2026-03-09"), 2); // across the spring clock change
+  assert.equal(addDays("2026-10-08", -182), "2026-04-09");
+  assert.equal(addDays("2026-01-01", -182), "2025-07-03");
+  assert.equal(addDays("2028-02-28", 2), "2028-03-01");
+});
````

Create `tests/web/svg.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { linePath, n, scale } from "../../solar_clock/web/js/svg.js";
import { HOSTILE } from "./fixtures.mjs";

test("n() writes short numbers and never passes text through", () => {
  assert.equal(n(12.34), "12.3");
  assert.equal(n(12), "12");
  assert.equal(n(-0.04), "0");
  assert.equal(n(HOSTILE), "NaN");
  assert.equal(n(null), "0");
});

test("scale() maps a data range onto a pixel range, either way up", () => {
  const y = scale(40, -90, 56, 176); // the Sun Path chart: 40° on top
  assert.equal(y(40), 56);
  assert.equal(y(-90), 176);
  assert.equal(n(y(0)), "92.9");
  assert.ok(y(73) < 56); // above the range lands above the box
});

test("linePath() joins points and is empty when there is no line", () => {
  assert.equal(linePath([[0, 1.26], [10, 2], [20.55, 3]]), "M0 1.3L10 2L20.6 3");
  assert.equal(linePath([[5, 5]]), "");
  assert.equal(linePath([]), "");
});
```

Apply this change to `tests/web/fixtures.mjs` (sample charts, added just above `HOSTILE`):

````diff
--- a/tests/web/fixtures.mjs
+++ b/tests/web/fixtures.mjs
@@ -89,6 +89,61 @@ export function sampleNow() {
   return structuredClone(SAMPLE);
 }

+const DAY_MS = 86_400_000;
+const TURN = 2 * Math.PI;
+const round = (value, digits) => Number(value.toFixed(digits));
+const dayOf2026 = (day) => new Date(Date.UTC(2026, 0, 1) + day * DAY_MS).toISOString().slice(0, 10);
+
+/** The equation of time in minutes for a day of the year (textbook approximation). */
+function equationOfTime(day) {
+  const b = (TURN * (day - 81)) / 364;
+  return 9.87 * Math.sin(2 * b) - 7.53 * Math.cos(b) - 1.5 * Math.sin(b);
+}
+
+// A /api/charts response for the same day. The curves are smooth stand-ins
+// with the real shapes and sizes (48, 122 and 53 samples), not real astronomy;
+// tests/test_web_contract.py feeds the views the real thing.
+const CHARTS = {
+  date: "2026-10-08",
+  sun_path: {
+    step_minutes: 30,
+    // Highest (43°) at 12:45 PM, lowest (-55°) at 12:45 AM.
+    elevations: Array.from({ length: 48 }, (_, i) =>
+      round(-6 + 49 * Math.cos((TURN * (i * 30 - 765)) / 1440), 2)),
+  },
+  day_length: {
+    year: 2026,
+    points: Array.from({ length: 122 }, (_, i) =>
+      [i * 3, round(12.17 + 2.92 * Math.sin((TURN * (i * 3 - 80)) / 365), 3)]),
+    shortest: { date: "2026-12-21", hours: 9.245021295277779 },
+    longest: { date: "2026-06-21", hours: 15.086548289166666 },
+    events: [
+      { name: "Vernal", date: "2026-03-20" },
+      { name: "Summer", date: "2026-06-21" },
+      { name: "Autumn", date: "2026-09-23" },
+      { name: "Winter", date: "2026-12-21" },
+    ],
+  },
+  analemma: {
+    points: Array.from({ length: 53 }, (_, week) => ({
+      date: dayOf2026(week * 7),
+      elevation: round(49.3 + 23.4 * Math.sin((TURN * (week * 7 - 80)) / 365), 2),
+      equation_of_time: round(equationOfTime(week * 7), 2),
+    })),
+    equation_of_time: 12.733333333333348,
+  },
+};
+
+/** A fresh copy of the sample charts, safe to modify in a test. */
+export function sampleCharts() {
+  return structuredClone(CHARTS);
+}
+
+/** What app.js hands a view: the /api/now sample with the charts attached. */
+export function samplePage() {
+  return { ...sampleNow(), charts: sampleCharts() };
+}
+
 /** Every string that must never reach the page unescaped. */
 export const HOSTILE = '<img src=x onerror="alert(1)">';

````

- [ ] **Step 2: Run them and watch them fail**

Run: `node --test tests/web/*.test.mjs`
Expected: 2 failures. `format.test.mjs` fails with `does not provide an export named 'addDays'` and `svg.test.mjs` with `ERR_MODULE_NOT_FOUND`. The other 34 tests pass.

- [ ] **Step 3: Implement.** Apply this change to `solar_clock/web/js/format.js`:

````diff
--- a/solar_clock/web/js/format.js
+++ b/solar_clock/web/js/format.js
@@ -79,6 +79,39 @@ export function longDate(now, timeZone) {
   return `${z.weekday}, ${MONTHS[z.month - 1]} ${pad2(z.day)}, ${z.year}`;
 }

+/** "%a %b %d", e.g. "Thu Oct 08" (Sun Path view). */
+export function shortWeekdayDate(now, timeZone) {
+  const z = zoned(now, timeZone);
+  return `${z.weekday.slice(0, 3)} ${MONTHS[z.month - 1].slice(0, 3)} ${pad2(z.day)}`;
+}
+
+/** "%A, %B %d", e.g. "Thursday, October 08" (Analog Clock view). */
+export function weekdayDate(now, timeZone) {
+  const z = zoned(now, timeZone);
+  return `${z.weekday}, ${MONTHS[z.month - 1]} ${pad2(z.day)}`;
+}
+
+/** The "YYYY-MM-DD" date of an instant in `timeZone`. */
+export function isoDate(value, timeZone) {
+  const z = zoned(value, timeZone);
+  return `${z.year}-${pad2(z.month)}-${pad2(z.day)}`;
+}
+
+function utcDay(isoDay) {
+  const [year, month, day] = isoDay.split("-").map(Number);
+  return Date.UTC(year, month - 1, day);
+}
+
+/** Whole days from one "YYYY-MM-DD" date to another; negative when `to` is earlier. */
+export function daysBetween(from, to) {
+  return Math.round((utcDay(to) - utcDay(from)) / 86_400_000);
+}
+
+/** The "YYYY-MM-DD" date `days` after (or, when negative, before) another. */
+export function addDays(isoDay, days) {
+  return new Date(utcDay(isoDay) + days * 86_400_000).toISOString().slice(0, 10);
+}
+
 /** "%b %d" for a "YYYY-MM-DD" date, e.g. "Oct 10". */
 export function shortDate(isoDate) {
   const [, month, day] = isoDate.split("-").map(Number);
````

Create `solar_clock/web/js/svg.js`:

```js
// Small helpers for the chart views' inline SVG.

/** A number as SVG attribute text: one decimal at most, e.g. 12.34 -> "12.3". */
export function n(value) {
  return String(Math.round(Number(value) * 10) / 10);
}

/** A function mapping the range d0..d1 onto r0..r1 in a straight line. */
export function scale(d0, d1, r0, r1) {
  return (value) => r0 + ((value - d0) / (d1 - d0)) * (r1 - r0);
}

/** Path data for a line through [[x, y], ...]; "" when there is nothing to join. */
export function linePath(points) {
  if (points.length < 2) return "";
  return points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${n(x)} ${n(y)}`).join("");
}
```

- [ ] **Step 4: Run the tests**

Run: `node --test tests/web/*.test.mjs` and `./venv/bin/pytest -q`
Expected: JS 50 pass, 0 fail; Python `322 passed, 3 skipped` (`test_web_page_files.py` checks that the new file's imports are served).

- [ ] **Step 5: Commit**

```bash
git add solar_clock/web/js/format.js solar_clock/web/js/svg.js tests/web/
git commit -m "Add date and SVG helpers for the web page's chart views" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Sun Path and Day Length views

**Files:**
- Create: `solar_clock/web/js/views/sunpath.js`, `solar_clock/web/js/views/daylength.js`, `tests/web/sunpath.test.mjs`, `tests/web/daylength.test.mjs`
- Modify: `solar_clock/web/js/views/index.js`, `solar_clock/web/style.css`
- Rewrite: `tests/web/views.test.mjs` (phase 1's four tests, now fed `samplePage()`, plus one new test)

**Interfaces:**
- Consumes: the Task 3 helpers; from phase 1 `countdownHM`, `dayLengthPadded`, `dayLengthText`, `escapeHtml`, `fixed`, `shortDate`, `time12`, `zoned` (`format.js`) and `namedColors` (`theme.js`).
- Produces: views `sunpath` ("Sun Path") and `daylength` ("Day Length"), each exporting `name`, `title` and `render(data, now) -> string`. After this task the order is `clock, weather, airquality, sunpath, daylength, solar, moon`.
- **The charts reach a view as `data.charts`.** It is `null` or missing until `/api/charts` has answered (and stays so until Task 6 wires it up), and each chart inside it may be `null`. A view must draw its frame and text either way.

TFT behaviours these views copy (from `sunpath.py` and `daylength.py`):
- **Sun Path:**
  - The time ("3:12 PM") and date ("Thu Oct 08") sit in the top corners.
  - The chart's scale runs from 40° at the top line to -90° at the bottom, with the horizon drawn at 0° and hour labels 00, 06, 12, 18, 24.
  - A piece of the curve is dark blue (`DARK_BLUE`) when both its ends are below the horizon, and the sun accent otherwise.
  - The marker sits at the current time of day and the current elevation from `/api/now`.
  - The left box shows "Solar Noon" until it has passed, then the next event: "Sunset in 3h 23m" and "at 6:35 PM". The right box shows "El 31°" and "Az 223°".
- **Day Length:**
  - The year is turned so today is in the middle of the chart; month letters (Ja, F, Mr, ...) start about six months back.
  - The scale is 9 to 15 hours with labels at 14h, 12h and 10h; the curve is clamped to the box.
  - "Today" shows "11h 30m" (not zero-padded) and the change as "-2.1m/day": sun accent when positive, cool accent otherwise, hidden when zero.
  - "Shortest" and "Longest" show the solstice day lengths zero-padded ("15h 05m") with their dates ("Jun 21").
  - "Next" shows the first of Vernal, Summer, Autumn, Winter after today, its date and the days to go. After the winter solstice it is empty.

Where the page differs from the TFT on purpose: the Sun Path picture grows upwards when the sun climbs past 40° (Review Focus 5), and countdowns stop at zero instead of vanishing (the spec's rule).

- [ ] **Step 1: Write the failing tests**

Create `tests/web/sunpath.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { render } from "../../solar_clock/web/js/views/sunpath.js";
import { NOW, assertShows, samplePage } from "./fixtures.mjs";

test("sun path view matches the TFT's text", () => {
  assertShows(render(samplePage(), NOW), [
    "Sun Path", "3:12 PM", "Thu Oct 08", ">40°<", ">0°<", ">-90°<", ">00<", ">06<", ">24<",
    "Sunset", "in 3h 23m", "at 6:35 PM", "El 31°", "Az 223°",
    'stroke="#191970"', "stroke:var(--accent-sun)",
  ]);
});

test("before solar noon it counts down to solar noon, then to the next event", () => {
  const morning = new Date("2026-10-08T09:00:00-04:00");
  assertShows(render(samplePage(), morning), ["Solar Noon", "in 3h 52m", "at 12:52 PM"]);
  assert.ok(!render(samplePage(), NOW).includes("Solar Noon"));
});

test("the marker sits at the clock's time of day and the sun's height", () => {
  // 3:12 PM is 912 minutes into the day; the sample sun is 31.42° up.
  assertShows(render(samplePage(), NOW), ['<circle cx="232.7" cy="63.9" r="6"']);
  const data = samplePage();
  data.location.timezone = "Asia/Tokyo"; // the same instant is 4:12 AM there
  assertShows(render(data, NOW), ['<circle cx="86" cy="63.9" r="6"']);
});

test("the night part of the curve is dark blue and the day part is sun-coloured", () => {
  const data = samplePage();
  data.charts.sun_path = { step_minutes: 360, elevations: [-50, -10, 30, -10] };
  const html = render(data, NOW);
  assertShows(html, [
    '<path d="M30 139.1L110 102.2" fill="none" stroke="#191970"',
    '<path d="M110 102.2L190 65.2M190 65.2L270 102.2" fill="none" style="stroke:var(--accent-sun)"',
  ]);
});

test("the picture grows upwards to hold a summer sun above the 40° line", () => {
  assertShows(render(samplePage(), NOW), ['viewBox="0 43 360 153"']); // 43° at most
  const summer = samplePage();
  summer.charts.sun_path.elevations[25] = 73;
  assertShows(render(summer, NOW), ['viewBox="0 15 360 181"', "L196.7 25.5"]);
  const live = samplePage();
  live.sun.position.elevation = 73; // the live reading counts too
  assertShows(render(live, NOW), ['viewBox="0 15 360 181"', 'cy="25.5"']);
});

test("a missing sample breaks the line, not the view", () => {
  const data = samplePage();
  data.charts.sun_path.elevations[10] = null;
  const html = render(data, NOW);
  assert.ok(!html.includes("NaN"));
  assert.ok(!html.includes("96.7 118.5")); // the sample at 5:00 AM is gone
});

test("without the charts it still draws the axes, the marker and the boxes", () => {
  const data = samplePage();
  data.charts = null;
  const html = render(data, NOW);
  assertShows(html, [">0°<", "<circle", "El 31°", "Sunset"]);
  assert.ok(!html.includes("<path"));
});

test("without sun data it shows the empty chart and empty boxes, like the TFT", () => {
  const data = samplePage();
  data.sun = null;
  const html = render(data, NOW);
  assertShows(html, ["Sun Path", ">0°<", "<path"]);
  assert.ok(!html.includes("<circle"));
  assert.ok(!html.includes(" in "));
});
```

Create `tests/web/daylength.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { render } from "../../solar_clock/web/js/views/daylength.js";
import { NOW, assertShows, samplePage } from "./fixtures.mjs";

const at = (iso) => new Date(iso);

test("day length view matches the TFT's text", () => {
  assertShows(render(samplePage(), NOW), [
    "Day Length", ">14h<", ">12h<", ">10h<", "Today", "11h 30m", "-2.1m/day",
    "Shortest", "9h 14m", "Dec 21", "Longest", "15h 05m", "Jun 21",
    "Next", "Winter", ">74<", "days", 'stroke="#ff8c00"',
  ]);
});

test("today sits in the middle: its dot, and its month under it", () => {
  const html = render(samplePage(), NOW);
  // 11.5 hours on the 9-15 hour scale; October in the centre, April at the left edge.
  assertShows(html, ['<circle cx="190" cy="68.3" r="4"', '<text x="30" y="124">Ap</text>', '<text x="190" y="124">O</text>']);
});

test("the curve is turned around today and kept inside the box", () => {
  const data = samplePage();
  // 8 Oct is day 280. Day 280 lands mid-chart, day 100 just right of the left
  // edge and day 0 (1 Jan) to the right; 20 h and 5 h are off the 9-15 h scale.
  data.charts.day_length.points = [[0, 20], [100, 5], [280, 12]];
  assertShows(render(data, NOW), ['<path d="M31.8 110L189.6 60L264.1 10"']);
});

test("a growing day shows a plus sign in the sun colour", () => {
  const data = samplePage();
  data.sun.day_length_change_min = 1.26;
  assertShows(render(data, NOW), ['<span class="small sun">+1.3m/day</span>']);
  assertShows(render(samplePage(), NOW), ['<span class="small cool">-2.1m/day</span>']);
});

test("the next event is the first one after today", () => {
  assertShows(render(samplePage(), at("2026-03-20T12:00:00-04:00")), ["Summer", ">93<"]);
  assertShows(render(samplePage(), at("2026-12-20T12:00:00-05:00")), ["Winter", ">1<"]);
});

test("after the winter solstice the Next box is empty, as on the TFT", () => {
  const html = render(samplePage(), at("2026-12-25T12:00:00-05:00"));
  assertShows(html, ["Next", '<text x="30" y="124">Jn</text>']);
  assert.ok(!html.includes("days"));
});

test("year ends and leap years draw without gaps in the text", () => {
  for (const day of ["2026-12-31T23:59:59-05:00", "2027-01-01T00:00:00-05:00", "2028-02-29T12:00:00-05:00", "2028-12-31T12:00:00-05:00"]) {
    const html = render(samplePage(), at(day));
    for (const broken of ["NaN", "undefined", "Invalid"]) assert.ok(!html.includes(broken), `${day}: ${broken}`);
    assert.equal(html.match(/<text[^>]*y="124">/g).length, 12, day);
  }
});

test("a place where the sun doesn't set on the solstice shows the dates alone", () => {
  const data = samplePage();
  data.charts.day_length.shortest.hours = null;
  data.charts.day_length.longest.hours = null;
  const html = render(data, NOW);
  assertShows(html, ["Dec 21", "Jun 21"]);
  assert.ok(!html.includes("NaN"));
  assert.ok(!html.includes("nowrap"));
});

test("without the charts or sun data it keeps its frame", () => {
  const data = samplePage();
  data.charts = null;
  data.sun = null;
  const html = render(data, NOW);
  assertShows(html, ["Day Length", ">12h<", "Today", "Shortest", "Longest", "Next"]);
  for (const absent of ["<path", "<circle", "undefined", "days"]) assert.ok(!html.includes(absent), absent);
});
```

Replace the whole of `tests/web/views.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { VIEWS } from "../../solar_clock/web/js/views/index.js";
import { HOSTILE, NOW, samplePage } from "./fixtures.mjs";

test("views come in TFT order and each has a name, title and render()", () => {
  assert.deepEqual(VIEWS.map((v) => v.name), [
    "clock", "weather", "airquality", "sunpath", "daylength", "solar", "moon",
  ]);
  for (const view of VIEWS) {
    assert.equal(typeof view.title, "string");
    assert.equal(typeof view.render(samplePage(), NOW), "string");
  }
});

test("every view renders when every data section is null", () => {
  const empty = samplePage();
  for (const key of ["theme", "sun", "weather", "air_quality", "moon", "charts"]) empty[key] = null;
  for (const view of VIEWS) assert.equal(typeof view.render(empty, NOW), "string", view.name);
});

test("every view renders when the charts arrived but each chart is null", () => {
  const data = samplePage();
  for (const key of ["sun_path", "day_length", "analemma"]) data.charts[key] = null;
  for (const view of VIEWS) {
    const html = view.render(data, NOW);
    assert.ok(!html.includes("undefined") && !html.includes("NaN"), view.name);
  }
});

test("text from the API is escaped in every view", () => {
  const data = samplePage();
  data.location.name = HOSTILE;
  data.weather.current.description = HOSTILE;
  data.weather.current.wind_direction = HOSTILE;
  data.air_quality.category = HOSTILE;
  data.sun.next_event.name = HOSTILE;
  data.moon.phase.phase_name = HOSTILE;
  for (const event of data.charts.day_length.events) event.name = HOSTILE;
  for (const view of VIEWS) {
    assert.ok(!view.render(data, NOW).includes("<img"), `${view.name} let markup through`);
  }
});

test("numbers and colours from the API can't carry markup either", () => {
  const data = samplePage();
  for (const key of Object.keys(data.theme.colors)) data.theme.colors[key] = HOSTILE;
  data.weather.current.humidity = HOSTILE;
  for (const day of data.weather.forecast) day.rain_chance = HOSTILE;
  data.air_quality.aqi = HOSTILE;
  data.moon.phase.days_to_new = HOSTILE;
  data.moon.phase.days_to_full = HOSTILE;
  data.charts.sun_path.step_minutes = HOSTILE;
  data.charts.sun_path.elevations = data.charts.sun_path.elevations.map(() => HOSTILE);
  data.charts.day_length.points = data.charts.day_length.points.map(() => [HOSTILE, HOSTILE]);
  for (const point of data.charts.analemma.points) {
    point.elevation = HOSTILE;
    point.equation_of_time = HOSTILE;
  }
  for (const view of VIEWS) {
    assert.ok(!view.render(data, NOW).includes("<img"), `${view.name} let markup through`);
  }
});
```

- [ ] **Step 2: Run them and watch them fail**

Run: `node --test tests/web/*.test.mjs`
Expected: 3 failures. `sunpath.test.mjs` and `daylength.test.mjs` fail with `ERR_MODULE_NOT_FOUND`, and the `views.test.mjs` order test fails because the list still has five views.

- [ ] **Step 3: Implement**

Create `solar_clock/web/js/views/sunpath.js`:

```js
// Sun Path view: mirrors solar_clock/views/sunpath.py.

import { countdownHM, escapeHtml, fixed, shortWeekdayDate, time12, zoned } from "../format.js";
import { n, scale } from "../svg.js";
import { namedColors } from "../theme.js";

export const name = "sunpath";
export const title = "Sun Path";

// The chart box, in SVG units. The scale is the TFT's: 40° on the top line and
// -90° on the bottom one. A summer sun climbs past 40° (on the TFT that part
// of the curve runs up into the header), so the picture grows upwards to fit.
const LEFT = 30;
const RIGHT = 350;
const TOP = 56;
const BOTTOM = 176;
const xAt = scale(0, 24 * 60, LEFT, RIGHT);
const yAt = scale(40, -90, TOP, BOTTOM);

export function render(data, now) {
  const colors = namedColors(data);
  const tz = data.location.timezone;
  return `<header class="view-header" style="background:${colors.ORANGE}"><h2>Sun Path</h2></header>
<div class="view-body">
  <p class="corners"><span>${time12(now, tz)}</span><span>${shortWeekdayDate(now, tz)}</span></p>
  ${chart(data, now, colors, tz)}
  <div class="row">
    ${eventPanel(data.sun, now, tz)}
    ${positionPanel(data.sun?.position)}
  </div>
</div>`;
}

function chart(data, now, colors, tz) {
  const path = data.charts?.sun_path;
  const position = data.sun?.position;
  const highest = Math.max(40, position?.elevation ?? 40, ...(path?.elevations ?? []));
  const top = Math.floor(yAt(highest)) - 10;
  const horizon = n(yAt(0));
  const hours = [0, 6, 12, 18, 24]
    .map((h) => `<text x="${n(xAt(h * 60))}" y="${BOTTOM + 14}" text-anchor="middle">${String(h).padStart(2, "0")}</text>`)
    .join("");
  return `<svg class="chart" viewBox="0 ${top} 360 ${BOTTOM + 20 - top}" role="img" aria-label="Sun elevation through the day">
    <text x="${LEFT - 4}" y="${TOP + 4}" text-anchor="end">40°</text>
    <text x="${LEFT - 4}" y="${n(yAt(0) + 4)}" text-anchor="end">0°</text>
    <text x="${LEFT - 4}" y="${BOTTOM - 2}" text-anchor="end">-90°</text>
    ${hours}
    <line class="axis" x1="${LEFT}" y1="${horizon}" x2="${RIGHT}" y2="${horizon}" stroke-width="2.5"/>
    ${curve(path, colors)}
    ${marker(position, now, tz)}
  </svg>`;
}

/** The day's curve: dark blue while the sun is down, the sun colour while it is up. */
function curve(path, colors) {
  if (!path) return "";
  const points = path.elevations.map((elevation, i) =>
    elevation === null ? null : { x: xAt(i * path.step_minutes), y: yAt(elevation), up: elevation >= 0 },
  );
  let down = "";
  let up = "";
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (a === null || b === null) continue;
    const piece = `M${n(a.x)} ${n(a.y)}L${n(b.x)} ${n(b.y)}`;
    if (a.up || b.up) up += piece;
    else down += piece;
  }
  return `<path d="${down}" fill="none" stroke="${colors.DARK_BLUE}" stroke-width="3" stroke-linecap="round"/>
    <path d="${up}" fill="none" style="stroke:var(--accent-sun)" stroke-width="3" stroke-linecap="round"/>`;
}

function marker(position, now, tz) {
  if (!position) return "";
  const z = zoned(now, tz);
  return `<circle cx="${n(xAt(z.hour * 60 + z.minute))}" cy="${n(yAt(position.elevation))}" r="6" style="fill:var(--accent-sun);stroke:var(--accent-warm)"/>`;
}

// Solar noon until it has passed, then whatever comes next.
function eventPanel(sun, now, tz) {
  let event = sun?.next_event ?? null;
  if (sun?.times?.noon && new Date(sun.times.noon) > now) event = { name: "Solar Noon", at: sun.times.noon };
  if (!event) return `<section class="panel"></section>`;
  const left = countdownHM(event.at, now);
  return `<section class="panel">
      <span class="warm">${escapeHtml(event.name)} <span class="primary">in ${left.h}h ${left.m}m</span></span>
      <span class="secondary">at ${time12(event.at, tz)}</span>
    </section>`;
}

function positionPanel(position) {
  const body = position
    ? `<span class="value sun">El ${fixed(position.elevation)}°</span><span class="secondary small">Az ${fixed(position.azimuth)}°</span>`
    : "";
  return `<section class="panel">${body}</section>`;
}
```

Create `solar_clock/web/js/views/daylength.js`:

```js
// Day Length view: mirrors solar_clock/views/daylength.py.

import {
  addDays, dayLengthPadded, dayLengthText, daysBetween, escapeHtml, fixed, isoDate, shortDate,
} from "../format.js";
import { linePath, n, scale } from "../svg.js";
import { namedColors } from "../theme.js";

export const name = "daylength";
export const title = "Day Length";

// The chart box, in SVG units: 9 to 15 hours of daylight, as on the TFT.
const LEFT = 30;
const RIGHT = 350;
const TOP = 10;
const BOTTOM = 110;
const HALF_YEAR = 182;
const MONTHS = ["Ja", "F", "Mr", "Ap", "My", "Jn", "Jl", "Au", "S", "O", "N", "D"];
const xAt = scale(0, 365, LEFT, RIGHT);
const yAt = scale(9, 15, BOTTOM, TOP);

export function render(data, now) {
  const colors = namedColors(data);
  const today = isoDate(now, data.location.timezone);
  const yearly = data.charts?.day_length;
  return `<header class="view-header" style="background:${colors.ORANGE}"><h2>Day Length</h2></header>
<div class="view-body">
  ${chart(yearly, data.sun, today, colors)}
  <div class="row">
    ${todayPanel(data.sun)}
    ${extremesPanel(yearly)}
    ${nextPanel(yearly, today)}
  </div>
</div>`;
}

// The year is turned so that today sits in the middle of the chart.
function chart(yearly, sun, today, colors) {
  const hourLabels = [14, 12, 10]
    .map((h) => `<text x="${LEFT - 4}" y="${n(yAt(h) + 4)}" text-anchor="end">${h}h</text>`)
    .join("");
  const firstMonth = Number(addDays(today, -HALF_YEAR).slice(5, 7)) - 1;
  const monthLabels = MONTHS.map((_, i) =>
    `<text x="${n(xAt((i / 12) * 365))}" y="${BOTTOM + 14}">${MONTHS[(firstMonth + i) % 12]}</text>`,
  ).join("");
  return `<svg class="chart" viewBox="0 0 360 128" role="img" aria-label="Day length through the year">
    ${hourLabels}
    ${monthLabels}
    ${curve(yearly, today, colors)}
    ${todayDot(sun)}
  </svg>`;
}

function curve(yearly, today, colors) {
  if (!yearly) return "";
  const shift = daysBetween(`${today.slice(0, 4)}-01-01`, today) - HALF_YEAR;
  const points = yearly.points
    .map(([day, hours]) => [
      xAt((((day - shift) % 365) + 365) % 365),
      Math.max(TOP, Math.min(BOTTOM, yAt(hours))),
    ])
    .sort((a, b) => a[0] - b[0]);
  return `<path d="${linePath(points)}" fill="none" stroke="${colors.ORANGE}" stroke-width="1.5"/>`;
}

function todayDot(sun) {
  if (!sun?.day_length_hours) return "";
  return `<circle cx="${(LEFT + RIGHT) / 2}" cy="${n(yAt(sun.day_length_hours))}" r="4" style="fill:var(--text-primary);stroke:var(--accent-sun)"/>`;
}

function todayPanel(sun) {
  const length = sun?.day_length_hours
    ? `<span class="value">${dayLengthText(sun.day_length_hours)}</span>`
    : "";
  const change = sun?.day_length_change_min;
  const changeText = change
    ? `<span class="small ${change > 0 ? "sun" : "cool"}">${change > 0 ? "+" : ""}${fixed(change, 1)}m/day</span>`
    : "";
  return `<section class="panel"><span class="label">Today</span>${length}${changeText}</section>`;
}

function extremesPanel(yearly) {
  const column = (label, day, tone) => {
    const hours = day && day.hours !== null ? `<span class="${tone} nowrap">${dayLengthPadded(day.hours)}</span>` : "";
    const date = day ? `<span class="secondary small">${shortDate(day.date)}</span>` : "";
    return `<div class="stat"><span class="label small">${label}</span>${hours}${date}</div>`;
  };
  return `<section class="panel pair">
      ${column("Shortest", yearly?.shortest, "cool")}
      ${column("Longest", yearly?.longest, "warm")}
    </section>`;
}

// The next solstice or equinox this year; after the winter solstice the box is empty.
function nextPanel(yearly, today) {
  const next = yearly?.events.find((event) => daysBetween(today, event.date) > 0);
  const body = next
    ? `<div class="pair">
        <div class="stat"><span class="green">${escapeHtml(next.name)}</span><span class="secondary small">${shortDate(next.date)}</span></div>
        <div class="stat"><span class="value">${daysBetween(today, next.date)}</span><span class="label small">days</span></div>
      </div>`
    : "";
  return `<section class="panel"><span class="label">Next</span>${body}</section>`;
}
```

Replace the whole of `solar_clock/web/js/views/index.js`:

```js
// Views in the same order as the TFT (solar_clock/views/__init__.py).

import * as airquality from "./airquality.js";
import * as clock from "./clock.js";
import * as daylength from "./daylength.js";
import * as moon from "./moon.js";
import * as solar from "./solar.js";
import * as sunpath from "./sunpath.js";
import * as weather from "./weather.js";

export const VIEWS = [
  clock, weather, airquality, sunpath, daylength, solar, moon,
];
```

Apply this change to `solar_clock/web/style.css` (one colour class, and the chart styles at the end):

````diff
--- a/solar_clock/web/style.css
+++ b/solar_clock/web/style.css
@@ -74,6 +74,7 @@ body {
 .warm { color: var(--accent-warm); }
 .cool { color: var(--accent-cool); }
 .moon { color: var(--accent-moon); }
+.green { color: var(--accent-green); }
 .message { padding: 48px 16px; color: var(--text-secondary); font-size: 18px; text-align: center; }
 .footer { display: flex; justify-content: space-between; gap: 12px; color: var(--text-tertiary); font-size: 14px; }

@@ -139,3 +140,12 @@ body {
 .cycle { position: relative; display: block; height: 10px; margin-top: 8px; background: var(--divider); }
 .cycle-fill { position: absolute; top: 0; bottom: 0; left: 0; }
 .cycle-full { position: absolute; top: -2px; bottom: -2px; left: 50%; width: 2px; background: var(--accent-moon); }
+
+/* Charts: Sun Path, Day Length, Analemma. Line widths are SVG attributes. */
+.chart { display: block; width: 100%; height: auto; overflow: visible; }
+.chart text { fill: var(--text-tertiary); font-size: 11px; }
+.chart .axis { stroke: var(--text-tertiary); }
+.chart .chart-message { fill: var(--text-secondary); font-size: 14px; }
+.corners { display: flex; justify-content: space-between; font-size: 14px; }
+.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
+.nowrap { font-size: 15px; white-space: nowrap; }
````

- [ ] **Step 4: Run the tests**

Run: `node --test tests/web/*.test.mjs` and `./venv/bin/pytest -q`
Expected: JS 68 pass, 0 fail; Python `322 passed, 3 skipped`.

- [ ] **Step 5: Commit**

```bash
git add solar_clock/web/ tests/web/
git commit -m "Add Sun Path and Day Length views to the web page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Analemma and Analog Clock views

**Files:**
- Create: `solar_clock/web/js/views/analemma.js`, `solar_clock/web/js/views/analogclock.js`, `tests/web/analemma.test.mjs`, `tests/web/analogclock.test.mjs`
- Modify: `solar_clock/web/js/views/index.js`, `solar_clock/web/style.css`, `tests/web/views.test.mjs` (the order assertion)

**Interfaces:**
- Consumes: as in Task 4, plus `weekdayDate`, `isoDate`, `daysBetween` (`format.js`), `timeOfDayHeader` (`theme.js`) and `n` (`svg.js`).
- Produces: views `analemma` ("Analemma") and `analogclock` ("Analog Clock"). The final order, matching `solar_clock/views/__init__.py`, is `clock, weather, airquality, sunpath, daylength, solar, moon, analemma, analogclock`.

TFT behaviours these views copy (from `analemma.py` and `analogclock.py`):
- **Analemma:**
  - The diagram uses the TFT's own mapping: 15 minutes of equation of time is 50 units across from the centre line, and 47° of noon elevation around 55° is 170 units of height.
  - Dots are coloured by month: March-May the green accent, June-August the sun accent, September-November the warm accent, the rest the cool accent.
  - Today's larger dot is the last weekly sample less than 7 days from today.
  - "Sun early" is printed on the left and "Sun late" on the right, as on the TFT. (See "For Peter" item 1: the TFT has these on the wrong sides. Copy it unless he has said to swap them.)
  - "Today" shows "Sun is", "12.7 min" and "early" (positive) or "late"; it is empty when the value is zero or missing.
  - "Sun path" shows "high" above 45° or "low", and the elevation as "31.4° S".
  - With no lunar data the TFT prints "Data unavailable". The page prints it when the charts have arrived without an analemma; while the charts are still loading it draws the bare axes.
- **Analog Clock:**
  - The whole view takes the time-of-day colour (the same rule as the Clock view's header), with "Analog" in the top-left corner and the date ("Thursday, October 08") under the face.
  - Long marks at 12, 3, 6 and 9; a thin mark and a dot at the other hours; small marks at the other minutes.
  - The hour hand is half the radius and creeps with the minutes. The minute hand is three-quarters of the radius and steps once a minute. The second hand is 85% of the radius, in red (200, 0, 0).

Layout: on a phone in portrait the Analemma's diagram sits above its boxes; on a wider screen they sit side by side as on the TFT (the existing `.row.wide` rule). The Analog Clock fills the view's height, which needs `.view` to become a flex column; phase 1's views are block content inside it and look the same.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/analemma.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { render } from "../../solar_clock/web/js/views/analemma.js";
import { NOW, assertShows, samplePage } from "./fixtures.mjs";

const count = (html, piece) => html.split(piece).length - 1;

test("analemma view matches the TFT's text", () => {
  const html = render(samplePage(), NOW);
  assertShows(html, [
    "Analemma", ">Summer<", ">winter<", ">early<", ">late<", "Today", "Sun is", "12.7 min",
    '<span class="secondary">early</span>', "Sun path", ">low<", "31.4° S",
    "Legend:", "Sp", "Su", "Fa", "Wi",
  ]);
  assert.equal(count(html, 'r="2"'), 53); // one dot per weekly sample
  assert.equal(count(html, 'r="6"'), 1); // and today's
});

test("a slow sun reads late, and a sun above 45° reads high", () => {
  const data = samplePage();
  data.charts.analemma.equation_of_time = -3.57;
  data.sun.position.elevation = 61.04;
  assertShows(render(data, NOW), ["3.6 min", '<span class="secondary">late</span>', ">high<", "61.0° S"]);
});

test("dots are placed and coloured by the TFT's rules", () => {
  const data = samplePage();
  data.charts.analemma.points = [
    { date: "2026-01-08", elevation: 31.5, equation_of_time: -6 },
    { date: "2026-04-09", elevation: 55, equation_of_time: 0 },
    { date: "2026-07-02", elevation: 78.5, equation_of_time: -15 },
    { date: "2026-10-08", elevation: 55, equation_of_time: 15 },
  ];
  assertShows(render(data, NOW), [
    '<circle cx="100" cy="180" r="2" style="fill:var(--accent-cool)"/>',
    '<circle cx="120" cy="95" r="2" style="fill:var(--accent-green)"/>',
    '<circle cx="70" cy="10" r="2" style="fill:var(--accent-sun)"/>',
    '<circle cx="170" cy="95" r="2" style="fill:var(--accent-warm)"/>',
    '<circle cx="170" cy="95" r="6" style="fill:var(--text-primary);stroke:var(--accent-sun)"/>',
  ]);
});

test("today's dot is the last sample less than a week away", () => {
  const data = samplePage();
  data.charts.analemma.points = [
    { date: "2026-10-01", elevation: 55, equation_of_time: 3 },
    { date: "2026-10-08", elevation: 55, equation_of_time: 6 },
    { date: "2026-10-15", elevation: 55, equation_of_time: 9 },
  ];
  assertShows(render(data, NOW), ['<circle cx="140" cy="95" r="6"']); // 8 Oct: the 15th is 7 days off
  const later = new Date("2026-10-11T12:00:00-04:00");
  assertShows(render(data, later), ['<circle cx="150" cy="95" r="6"']); // both near: the later one
  const spring = new Date("2026-04-01T12:00:00-04:00");
  assert.equal(count(render(data, spring), 'r="6"'), 0);
});

test("while the charts load it draws bare axes; without analemma data it says so", () => {
  const loading = samplePage();
  loading.charts = null;
  const bare = render(loading, NOW);
  assertShows(bare, [">Summer<", '<line class="axis"', "Today", "Sun path", "31.4° S"]);
  assert.ok(!bare.includes("Data unavailable"));
  assert.ok(!bare.includes("Sun is"));
  assert.equal(count(bare, "<circle"), 0);

  const unavailable = samplePage();
  unavailable.charts.analemma = null;
  assertShows(render(unavailable, NOW), ["Data unavailable"]);
});

test("without sun data the Sun path box is empty", () => {
  const data = samplePage();
  data.sun = null;
  const html = render(data, NOW);
  assertShows(html, ["Sun path", "12.7 min"]);
  assert.ok(!html.includes("° S"));
});
```

Create `tests/web/analogclock.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

import { render } from "../../solar_clock/web/js/views/analogclock.js";
import { NOW, assertShows, samplePage } from "./fixtures.mjs";

const count = (html, piece) => html.split(piece).length - 1;
const hand = (x, y, width) => `<line x1="110" y1="110" x2="${x}" y2="${y}" stroke-width="${width}"`;

test("analog clock shows the TFT's title, date and time-of-day colour", () => {
  assertShows(render(samplePage(), NOW), [
    "Analog", "Thursday, October 08", "background:#87ceeb", "fill:var(--clock-face)",
  ]);
});

test("the hands point at the time: 3:12:00", () => {
  // Hour hand 96° round from 12, 50 long; minute hand 72°, 75 long; second hand at 12.
  assertShows(render(samplePage(), NOW), [hand("159.7", "115.2", 6), hand("181.3", "86.8", 4), hand("110", "25", 2)]);
});

test("the minute hand steps once a minute, as on the TFT", () => {
  const html = render(samplePage(), new Date("2026-10-08T12:00:30-04:00"));
  assertShows(html, [hand("110", "60", 6), hand("110", "35", 4), hand("110", "195", 2)]);
});

test("the hands follow the clock's timezone, not the viewer's", () => {
  const data = samplePage();
  data.location.timezone = "Asia/Tokyo"; // the same instant is 4:12 AM there
  assertShows(render(data, NOW), [hand("150.5", "139.4", 6), hand("181.3", "86.8", 4)]);
});

test("the face has 4 long hour marks, 8 short ones with dots, and 48 minute marks", () => {
  const html = render(samplePage(), NOW);
  assert.equal(count(html, 'stroke-width="3" style="stroke:var(--clock-markers)"'), 4);
  assert.equal(count(html, 'stroke-width="1" style="stroke:var(--clock-markers)"'), 8);
  assert.equal(count(html, 'r="2" style="fill:var(--clock-markers)"'), 8);
  assert.equal(count(html, "stroke:var(--text-tertiary)"), 48);
});

test("without sun data the colour falls back to the hour of the day", () => {
  const data = samplePage();
  data.sun = null;
  assertShows(render(data, NOW), ["background:#87ceeb"]); // 3 PM
  assertShows(render(data, new Date("2026-10-08T22:00:00-04:00")), ["background:#9370db"]);
});
```

In `tests/web/views.test.mjs`, change the order assertion to the final list:

````diff
--- a/tests/web/views.test.mjs
+++ b/tests/web/views.test.mjs
@@ -6,7 +6,8 @@ import { HOSTILE, NOW, samplePage } from "./fixtures.mjs";

 test("views come in TFT order and each has a name, title and render()", () => {
   assert.deepEqual(VIEWS.map((v) => v.name), [
-    "clock", "weather", "airquality", "sunpath", "daylength", "solar", "moon",
+    "clock", "weather", "airquality", "sunpath", "daylength", "solar", "moon", "analemma",
+    "analogclock",
   ]);
   for (const view of VIEWS) {
     assert.equal(typeof view.title, "string");
````

- [ ] **Step 2: Run them and watch them fail**

Run: `node --test tests/web/*.test.mjs`
Expected: 3 failures. `analemma.test.mjs` and `analogclock.test.mjs` fail with `ERR_MODULE_NOT_FOUND`, and the `views.test.mjs` order test fails.

- [ ] **Step 3: Implement**

Create `solar_clock/web/js/views/analemma.js`:

```js
// Analemma view: mirrors solar_clock/views/analemma.py.

import { daysBetween, fixed, isoDate } from "../format.js";
import { n } from "../svg.js";
import { namedColors } from "../theme.js";

export const name = "analemma";
export const title = "Analemma";

// The TFT's diagram, in its own pixel coordinates: 15 minutes of equation of
// time is 50 units across, and 47° of noon elevation around 55° is 170 units.
const CX = 120;
const CY = 95;
const xAt = (minutes) => CX + (minutes / 15) * 50;
const yAt = (elevation) => CY - ((elevation - 55) / 47) * 170;

const SEASONS = [
  ["Sp", "spring", "var(--accent-green)"],
  ["Su", "summer", "var(--accent-sun)"],
  ["Fa", "fall", "var(--accent-warm)"],
  ["Wi", "winter", "var(--accent-cool)"],
];

function seasonColor(isoDay) {
  const month = Number(isoDay.slice(5, 7));
  const index = month >= 3 && month <= 5 ? 0 : month >= 6 && month <= 8 ? 1 : month >= 9 && month <= 11 ? 2 : 3;
  return SEASONS[index][2];
}

export function render(data, now) {
  const colors = namedColors(data);
  const today = isoDate(now, data.location.timezone);
  const charts = data.charts;
  return `<header class="view-header" style="background:${colors.ORANGE}"><h2>Analemma</h2></header>
<div class="view-body">
  <div class="row wide">
    ${diagram(charts, today)}
    <div class="analemma-info">
      ${todayPanel(charts?.analemma)}
      ${sunPathPanel(data.sun?.position)}
      ${legend()}
    </div>
  </div>
</div>`;
}

function diagram(charts, today) {
  // No answer yet draws the bare axes; an answer without analemma data says so.
  const body = charts && !charts.analemma
    ? `<text class="chart-message" x="${CX}" y="${CY - 30}" text-anchor="middle">Data unavailable</text>`
    : dots(charts?.analemma?.points ?? [], today);
  return `<svg class="chart analemma-chart" viewBox="0 0 240 212" role="img" aria-label="Analemma: the noon sun through the year">
      <text x="${CX}" y="10" text-anchor="middle" style="fill:var(--accent-sun)">Summer</text>
      <text x="${CX}" y="206" text-anchor="middle" style="fill:var(--accent-cool)">winter</text>
      <text x="5" y="${CY - 4}">Sun</text><text x="5" y="${CY + 16}">early</text>
      <text x="235" y="${CY - 4}" text-anchor="end">Sun</text><text x="235" y="${CY + 16}" text-anchor="end">late</text>
      <line class="axis" x1="${CX}" y1="20" x2="${CX}" y2="190"/>
      <line class="axis" x1="30" y1="${CY}" x2="210" y2="${CY}"/>
      ${body}
    </svg>`;
}

function dots(points, today) {
  let nearest = null;
  const circles = points.map((point) => {
    // As on the TFT, the last sample within a week of today is "today".
    if (Math.abs(daysBetween(point.date, today)) < 7) nearest = point;
    return `<circle cx="${n(xAt(point.equation_of_time))}" cy="${n(yAt(point.elevation))}" r="2" style="fill:${seasonColor(point.date)}"/>`;
  });
  const todayDot = nearest
    ? `<circle cx="${n(xAt(nearest.equation_of_time))}" cy="${n(yAt(nearest.elevation))}" r="6" style="fill:var(--text-primary);stroke:var(--accent-sun)"/>`
    : "";
  return circles.join("") + todayDot;
}

function todayPanel(analemma) {
  const minutes = analemma?.equation_of_time;
  const body = minutes
    ? `<span class="label">Sun is</span><span class="value big sun">${fixed(Math.abs(minutes), 1)} min</span><span class="secondary">${minutes > 0 ? "early" : "late"}</span>`
    : "";
  return `<section class="panel boxed"><h3 class="panel-title">Today</h3>${body}</section>`;
}

function sunPathPanel(position) {
  const body = position
    ? `<span class="value big sun">${position.elevation > 45 ? "high" : "low"}</span><span class="secondary">${fixed(position.elevation, 1)}° S</span>`
    : "";
  return `<section class="panel boxed"><h3 class="panel-title">Sun path</h3>${body}</section>`;
}

function legend() {
  const items = SEASONS.map(
    ([label, , color]) => `<span class="legend-item"><span class="legend-dot" style="background:${color}"></span>${label}</span>`,
  ).join("");
  return `<p class="legend"><span class="label small">Legend:</span>${items}</p>`;
}
```

Create `solar_clock/web/js/views/analogclock.js`:

```js
// Analog Clock view: mirrors solar_clock/views/analogclock.py.

import { weekdayDate, zoned } from "../format.js";
import { n } from "../svg.js";
import { namedColors, timeOfDayHeader } from "../theme.js";

export const name = "analogclock";
export const title = "Analog Clock";

const C = 110; // face centre in a 220 x 220 viewBox
const R = 100; // face radius, as on the TFT
const SECOND_HAND = "#c80000"; // (200, 0, 0), the TFT's second hand

/** The point `radius` out from the centre, `degrees` clockwise from 12 o'clock. */
function point(degrees, radius) {
  const angle = ((degrees - 90) * Math.PI) / 180;
  return [n(C + radius * Math.cos(angle)), n(C + radius * Math.sin(angle))];
}

function spoke(degrees, from, to, attributes) {
  const [x1, y1] = point(degrees, from);
  const [x2, y2] = point(degrees, to);
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${attributes}/>`;
}

export function render(data, now) {
  const tz = data.location.timezone;
  const background = timeOfDayHeader(now, data.sun, namedColors(data), tz);
  return `<div class="analog" style="background:${background}">
  <span class="analog-title">Analog</span>
  ${face(zoned(now, tz))}
  <p class="analog-date">${weekdayDate(now, tz)}</p>
</div>`;
}

function face(z) {
  return `<svg class="analog-face" viewBox="0 0 220 220" role="img" aria-label="Analog clock">
    <circle cx="${C}" cy="${C}" r="${R + 5}" stroke-width="3" style="fill:var(--clock-face);stroke:var(--outline)"/>
    ${markers()}
    ${hands(z)}
    <circle cx="${C}" cy="${C}" r="6" style="fill:var(--clock-hands)"/>
    <circle cx="${C}" cy="${C}" r="3" fill="${SECOND_HAND}"/>
  </svg>`;
}

// Long marks at 12, 3, 6 and 9; a thin mark and a dot at the other hours.
function markers() {
  const hourMark = `style="stroke:var(--clock-markers)"`;
  const marks = [];
  for (let minute = 0; minute < 60; minute += 1) {
    const degrees = minute * 6;
    if (minute % 5 !== 0) {
      marks.push(spoke(degrees, R - 8, R - 3, `stroke-width="1" style="stroke:var(--text-tertiary)"`));
    } else if (minute % 15 === 0) {
      marks.push(spoke(degrees, R - 15, R - 5, `stroke-width="3" ${hourMark}`));
    } else {
      const [cx, cy] = point(degrees, R - 10);
      marks.push(spoke(degrees, R - 15, R - 5, `stroke-width="1" ${hourMark}`));
      marks.push(`<circle cx="${cx}" cy="${cy}" r="2" style="fill:var(--clock-markers)"/>`);
    }
  }
  return marks.join("");
}

// As on the TFT, the minute hand steps once a minute; only the hour hand creeps.
function hands(z) {
  const hand = `stroke-linecap="round" style="stroke:var(--clock-hands)"`;
  return [
    spoke(((z.hour % 12) + z.minute / 60) * 30, 0, R * 0.5, `stroke-width="6" ${hand}`),
    spoke(z.minute * 6, 0, R * 0.75, `stroke-width="4" ${hand}`),
    spoke(z.second * 6, 0, R * 0.85, `stroke-width="2" stroke="${SECOND_HAND}"`),
  ].join("");
}
```

Replace the whole of `solar_clock/web/js/views/index.js`:

```js
// Views in the same order as the TFT (solar_clock/views/__init__.py).

import * as airquality from "./airquality.js";
import * as analemma from "./analemma.js";
import * as analogclock from "./analogclock.js";
import * as clock from "./clock.js";
import * as daylength from "./daylength.js";
import * as moon from "./moon.js";
import * as solar from "./solar.js";
import * as sunpath from "./sunpath.js";
import * as weather from "./weather.js";

export const VIEWS = [
  clock, weather, airquality, sunpath, daylength, solar, moon, analemma, analogclock,
];
```

Apply this change to `solar_clock/web/style.css`:

````diff
--- a/solar_clock/web/style.css
+++ b/solar_clock/web/style.css
@@ -47,7 +47,10 @@ body {
   font-size: 14px;
   text-align: center;
 }
-.view { flex: 1; width: 100%; max-width: 760px; margin: 0 auto; touch-action: pan-y; }
+.view {
+  flex: 1; display: flex; flex-direction: column;
+  width: 100%; max-width: 760px; margin: 0 auto; touch-action: pan-y;
+}
 .view-header {
   display: flex; align-items: baseline; justify-content: center; gap: 6px;
   padding: 8px 16px; color: #ffffff;
@@ -149,3 +152,17 @@ body {
 .corners { display: flex; justify-content: space-between; font-size: 14px; }
 .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
 .nowrap { font-size: 15px; white-space: nowrap; }
+
+/* Analemma: the diagram sits beside its panels on a wide screen, above them on a phone. */
+.value.big { font-size: 24px; white-space: nowrap; }
+.analemma-chart { max-width: 320px; margin: 0 auto; }
+.analemma-info { display: grid; align-content: start; gap: 10px; }
+.legend { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; color: var(--text-secondary); font-size: 12px; }
+.legend-item { display: inline-flex; align-items: center; gap: 4px; }
+.legend-dot { width: 8px; height: 8px; border-radius: 50%; }
+
+/* Analog clock: the whole view takes the time-of-day colour. */
+.analog { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 6px 16px 20px; }
+.analog-title { align-self: flex-start; color: var(--text-secondary); }
+.analog-face { width: 100%; max-width: 360px; max-height: 62vh; }
+.analog-date { margin: 0; font-size: 18px; }
````

- [ ] **Step 4: Run the tests**

Run: `node --test tests/web/*.test.mjs` and `./venv/bin/pytest -q`
Expected: JS 80 pass, 0 fail; Python `322 passed, 3 skipped`.

- [ ] **Step 5: Commit**

```bash
git add solar_clock/web/ tests/web/
git commit -m "Add Analemma and Analog Clock views to the web page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Load the charts in the page shell

Until now the chart views draw only their frames, because nothing fetches `/api/charts`. This task makes `app.js` fetch it and hand it to the views.

**Files:**
- Modify: `solar_clock/web/js/app.js`, `tests/web/dom-stub.mjs`, `tests/web/app.test.mjs`, `tests/test_web_contract.py`

**Interfaces:**
- Consumes: `GET /api/charts` (Task 2); the views' `data.charts` (Tasks 4-5); `sampleCharts()` (Task 3).
- Produces:
  - `app.js` keeps `state.charts` and renders every view with `{ ...state.data, charts: state.charts }`.
  - After each successful `/api/now` poll, it fetches `/api/charts` if it has no charts or `charts.date` differs from the first 10 characters of `generated_at` (the clock's local date).
  - `installDom({ hash, responses, charts })`: the fake page now answers `/api/charts` from its own `charts` queue; a number in either queue is an HTTP error status.

Rules:
- **The date comes from the clock's answer, not the viewer's device**, so a phone with a wrong clock can't cause a refetch on every poll.
- **A failed charts request is not a lost clock.** It logs a warning, leaves the old charts (or none) in place, shows no banner, and is retried on the next poll.
- **No charts request while the clock can't be reached.**

- [ ] **Step 1: Write the failing tests.** Apply this change to `tests/web/dom-stub.mjs`:

````diff
--- a/tests/web/dom-stub.mjs
+++ b/tests/web/dom-stub.mjs
@@ -19,10 +19,11 @@ function eventTarget(extra = {}) {
 const GLOBALS = ["document", "window", "location", "history", "fetch", "setInterval"];

 /**
- * Install a fake page. `responses` are served to fetch() in order: an object
- * is a 200 JSON body, an Error is a network failure, null never answers.
+ * Install a fake page. `responses` are served to fetch("/api/now") in order,
+ * and `charts` to fetch("/api/charts"): an object is a 200 JSON body, an Error
+ * is a network failure, a number is that HTTP status, null never answers.
  */
-export function installDom({ hash = "", responses = [] } = {}) {
+export function installDom({ hash = "", responses = [], charts = [] } = {}) {
   const saved = Object.fromEntries(GLOBALS.map((name) => [name, globalThis[name]]));
   const elements = {};
   for (const id of ["banner", "view", "dots", "prev", "next"]) {
@@ -60,9 +61,10 @@ export function installDom({ hash = "", responses = [] } = {}) {
     },
     fetch(url, options) {
       fetchCalls.push({ url, options });
-      const next = responses.shift();
+      const next = (url === "/api/charts" ? charts : responses).shift();
       if (next === null || next === undefined) return new Promise(() => {});
       if (next instanceof Error) return Promise.reject(next);
+      if (typeof next === "number") return Promise.resolve({ ok: false, status: next });
       return Promise.resolve({ ok: true, status: 200, json: async () => next });
     },
     setInterval: () => 0,
@@ -73,6 +75,7 @@ export function installDom({ hash = "", responses = [] } = {}) {
     location,
     fetchCalls,
     responses,
+    charts,
     restore() {
       Object.assign(globalThis, saved);
     },
````

Apply this change to `tests/web/app.test.mjs`. One phase 1 assertion changes (the page now makes a charts request as well, so the test counts `/api/now` requests instead of all requests), and five tests are added at the end:

````diff
--- a/tests/web/app.test.mjs
+++ b/tests/web/app.test.mjs
@@ -3,7 +3,7 @@ import assert from "node:assert/strict";

 import { VIEWS } from "../../solar_clock/web/js/views/index.js";
 import { installDom, loadApp, settle } from "./dom-stub.mjs";
-import { sampleNow } from "./fixtures.mjs";
+import { sampleCharts, sampleNow } from "./fixtures.mjs";

 // Written against the view list, so it holds as views are added.
 const names = VIEWS.map((v) => v.name);
@@ -12,6 +12,14 @@ const nameAt = (i) => names[((i % names.length) + names.length) % names.length];
 let page;
 afterEach(() => page.restore());

+const callsTo = (url) => page.fetchCalls.filter((call) => call.url === url).length;
+
+/** Wake the page, which polls at once, and wait for the answers. */
+async function wake() {
+  document.dispatch("visibilitychange");
+  await settle();
+}
+
 function dayData() {
   const data = sampleNow();
   data.theme.active = "day";
@@ -42,7 +50,7 @@ test("losing the clock keeps the last data and says so, then recovers", async ()
   await loadApp();
   document.dispatch("visibilitychange"); // waking the page polls at once
   await settle();
-  assert.equal(page.fetchCalls.length, 2);
+  assert.equal(callsTo("/api/now"), 2);
   assert.equal(page.elements.banner.hidden, false);
   assert.match(page.elements.banner.textContent, /^Can't reach clock · last update \d{1,2}:\d\d [AP]M$/);
   assert.match(page.elements.view.innerHTML, /Sunrise/);
@@ -106,3 +114,62 @@ test("a view that throws shows a message instead of a blank page", async () => {
   page.elements.next.dispatch("click");
   assert.equal(page.location.hash, `#${nameAt(1)}`);
 });
+
+test("the charts are fetched once the clock answers, and drawn", async () => {
+  page = installDom({ hash: "#sunpath", responses: [sampleNow()], charts: [sampleCharts()] });
+  await loadApp();
+  assert.deepEqual(page.fetchCalls.map((call) => call.url), ["/api/now", "/api/charts"]);
+  assert.equal(page.fetchCalls[1].options.cache, "no-store");
+  assert.match(page.elements.view.innerHTML, /stroke="#191970"/); // the night part of the curve
+});
+
+test("a chart view draws its frame while the charts are still on their way", async () => {
+  page = installDom({ hash: "#daylength", responses: [sampleNow()], charts: [null] });
+  await loadApp();
+  assert.match(page.elements.view.innerHTML, /Today/);
+  assert.doesNotMatch(page.elements.view.innerHTML, /<path/);
+});
+
+test("the charts are fetched again only when the clock's date moves on", async () => {
+  const tomorrow = sampleNow();
+  tomorrow.generated_at = "2026-10-09T00:00:30-04:00";
+  const tomorrowsCharts = sampleCharts();
+  tomorrowsCharts.date = "2026-10-09";
+  tomorrowsCharts.sun_path = { step_minutes: 720, elevations: [-50, 30] };
+  page = installDom({
+    hash: "#sunpath",
+    responses: [sampleNow(), sampleNow(), tomorrow, tomorrow],
+    charts: [sampleCharts(), tomorrowsCharts],
+  });
+  await loadApp();
+  await wake(); // same day: the charts are kept
+  assert.equal(callsTo("/api/charts"), 1);
+  await wake(); // past midnight on the clock: new charts
+  assert.equal(callsTo("/api/charts"), 2);
+  assert.match(page.elements.view.innerHTML, /<path d="M30 139\.1L190 65\.2"/);
+  await wake();
+  assert.equal(callsTo("/api/charts"), 2);
+});
+
+test("a failed charts request leaves the page working and is tried again", async () => {
+  page = installDom({
+    hash: "#sunpath",
+    responses: [sampleNow(), sampleNow(), sampleNow()],
+    charts: [503, new Error("offline"), sampleCharts()],
+  });
+  await loadApp();
+  assert.equal(page.elements.banner.hidden, true); // the clock itself answered
+  assert.match(page.elements.view.innerHTML, /El 31°/);
+  assert.doesNotMatch(page.elements.view.innerHTML, /<path/);
+  await wake();
+  assert.doesNotMatch(page.elements.view.innerHTML, /<path/);
+  await wake();
+  assert.equal(callsTo("/api/charts"), 3);
+  assert.match(page.elements.view.innerHTML, /<path/);
+});
+
+test("the charts are not asked for while the clock can't be reached", async () => {
+  page = installDom({ responses: [new Error("offline")], charts: [sampleCharts()] });
+  await loadApp();
+  assert.equal(callsTo("/api/charts"), 0);
+});
````

Apply this change to `tests/test_web_contract.py`, so the real charts go through every view too:

````diff
--- a/tests/test_web_contract.py
+++ b/tests/test_web_contract.py
@@ -1,4 +1,4 @@
-"""The real /api/now JSON must render in every view of the page.
+"""The real /api/now and /api/charts JSON must render in every view of the page.

 The JavaScript tests use a hand-written sample; this test feeds the page's
 views the JSON that WebDataService actually builds, through Node.js, so a
@@ -22,10 +22,11 @@ NODE = shutil.which("node")
 RENDER_EVERY_VIEW = """
 let text = "";
 for await (const chunk of process.stdin) text += chunk;
-const data = JSON.parse(text);
+const { now, charts } = JSON.parse(text);
+const data = { ...now, charts };
 const { VIEWS } = await import(process.argv[1]);
 const out = {};
-for (const view of VIEWS) out[view.name] = view.render(data, new Date(data.generated_at));
+for (const view of VIEWS) out[view.name] = view.render(data, new Date(now.generated_at));
 process.stdout.write(JSON.stringify(out));
 """

@@ -65,7 +66,7 @@ def test_every_view_renders_the_real_api_response(sample_config, weather):
     service = WebDataService(
         sample_config, weather=weather(), theme_mode=lambda: "auto"
     )
-    payload = json.dumps(service.build_now())
+    payload = json.dumps({"now": service.build_now(), "charts": service.build_charts()})
     views_module = (WEB_DIR / "js" / "views" / "index.js").as_uri()
     result = subprocess.run(
         [NODE, "--input-type=module", "-e", RENDER_EVERY_VIEW, views_module],
@@ -81,3 +82,8 @@ def test_every_view_renders_the_real_api_response(sample_config, weather):
         assert html.strip(), f"{name} rendered nothing"
         for broken in ("undefined", "NaN", "Invalid Date"):
             assert broken not in html, f"{name} shows {broken!r}"
+    # The chart views drew their curves from the real charts, not just a frame.
+    assert rendered["sunpath"].count('<path d="M') == 2
+    assert '<path d="M' in rendered["daylength"]
+    assert rendered["analemma"].count('r="2"') >= 52  # one dot per weekly sample
+    assert 'r="6"' in rendered["analemma"]  # today's dot
````

- [ ] **Step 2: Run them and watch them fail**

Run: `node --test tests/web/*.test.mjs` and `./venv/bin/pytest tests/test_web_contract.py -q`
Expected:
- JS: 3 failures: "the charts are fetched once the clock answers, and drawn", "the charts are fetched again only when the clock's date moves on" and "a failed charts request leaves the page working and is tried again". The other 82 pass.
- Python: `2 passed`. The contract test is green already; see "How this plan was checked".

- [ ] **Step 3: Implement.** Apply this change to `solar_clock/web/js/app.js`:

````diff
--- a/solar_clock/web/js/app.js
+++ b/solar_clock/web/js/app.js
@@ -1,5 +1,6 @@
-// Page shell: polls /api/now, redraws the current view every second, and
-// handles navigation. It only reads from the clock; it never changes it.
+// Page shell: polls /api/now, fetches /api/charts once per day, redraws the
+// current view every second, and handles navigation. It only reads from the
+// clock; it never changes it.

 import { time12 } from "./format.js";
 import { indexFromHash, swipeDelta, wrapIndex } from "./nav.js";
@@ -19,6 +20,7 @@ const els = {

 const state = {
   data: null,
+  charts: null,
   lastOk: null,
   failing: false,
   theme: null,
@@ -60,7 +62,7 @@ function render() {
   if (state.data === null) return;
   const view = VIEWS[state.index];
   try {
-    els.view.innerHTML = view.render(state.data, new Date());
+    els.view.innerHTML = view.render({ ...state.data, charts: state.charts }, new Date());
   } catch (err) {
     console.error(`The ${view.name} view failed to draw`, err);
     els.view.innerHTML = `<p class="message">Couldn't draw this view</p>`;
@@ -80,6 +82,26 @@ async function poll() {
     state.failing = true;
   }
   render();
+  if (!state.failing && chartsAreStale()) await loadCharts();
+}
+
+// The clock works its charts out once per day, so they are fetched when the
+// page has none or the clock's date has moved on. The date comes from the
+// clock's answer, not this device, so a wrong phone clock can't cause refetching.
+function chartsAreStale() {
+  return state.charts === null || state.charts.date !== state.data.generated_at.slice(0, 10);
+}
+
+// A failure leaves the old charts (or none) in place; the next poll tries again.
+async function loadCharts() {
+  try {
+    const response = await fetch("/api/charts", { cache: "no-store" });
+    if (!response.ok) throw new Error(`HTTP ${response.status}`);
+    state.charts = await response.json();
+    render();
+  } catch (err) {
+    console.warn("Could not load the charts", err);
+  }
 }

 function go(delta) {
````

- [ ] **Step 4: Run the tests**

Run: `node --test tests/web/*.test.mjs` and `./venv/bin/pytest -q`
Expected: JS 85 pass, 0 fail; Python `322 passed, 3 skipped`.

- [ ] **Step 5: Lint the Python test.** Run:

```bash
./venv/bin/black --check solar_clock tests
./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503
./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
```

Expected: black reports nothing to change, flake8 prints nothing, and mypy prints only its two existing notes about `font_manager.py`.

- [ ] **Step 6: Commit**

```bash
git add solar_clock/web/js/app.js tests/web/ tests/test_web_contract.py
git commit -m "Load the charts into the web page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Docs, full verification and proof that the TFT is unchanged

**Files:**
- Modify: `README.md`, `CLAUDE.md`
- Scratch only, not committed: `<scratchpad>/parity/render_tft.py` and `compare.py`, copied out of the phase 1 plan

- [ ] **Step 1: Docs.** Apply these changes:

````diff
--- a/README.md
+++ b/README.md
@@ -152,6 +152,7 @@ The clock runs an HTTP server for remote control and screenshots.
 | `GET /health` | Health check (returns "OK") |
 | `GET /` | The web page |
 | `GET /api/now` | JSON behind the web page (read-only) |
+| `GET /api/charts` | Chart curves behind the web page (read-only) |

 **Note**: By default, the HTTP server only accepts connections from localhost. Use `--bind-all` flag or set `http_server.bind_address` to `"0.0.0.0"` for network access.

@@ -176,7 +177,8 @@ or use the arrow keys to change views. This never changes what the clock's own
 screen shows. Colours follow the clock's day/night theme. Use your browser's
 "Add to Home Screen" (phone) or "Create shortcut" (desktop) for an app icon.

-Views: Clock, Weather, Air Quality, Solar Details and Moon Phase.
+It has all nine views: Clock, Weather, Air Quality, Sun Path, Day Length, Solar
+Details, Moon Phase, Analemma and Analog Clock.

 ## Hardware Requirements

@@ -224,7 +226,7 @@ solar-clock/
 │   ├── display.py           # Framebuffer handling
 │   ├── http_server.py       # HTTP API server
 │   ├── touch_handler.py     # Touch input
-│   ├── web_api.py           # /api/now data for the web page
+│   ├── web_api.py           # /api/now and /api/charts data for the web page
 │   ├── web_static.py        # Serves the web page's files
 │   ├── web/                 # The web page (HTML, CSS, JavaScript modules, icons)
 │   ├── data/
````

````diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -52,6 +52,7 @@ The clock runs an HTTP server on port 8080 for fast remote screenshots.
 | `/view` | Get current view name and index |
 | `/` | The web page (phone-friendly copy of the views) |
 | `/api/now` | JSON for the web page (read-only) |
+| `/api/charts` | Chart curves for the web page (read-only, worked out once a day) |

 ### From Remote Machine

@@ -76,7 +77,7 @@ done

 `http://clock.local:8080/` serves a browser copy of the views from `solar_clock/web/`.

-- The page and `/api/now` must never change clock state: no `ViewManager` calls, never `set_mode` on the clock's ThemeManager.
+- The page, `/api/now` and `/api/charts` must never change clock state: no `ViewManager` calls, never `set_mode` on the clock's ThemeManager.
 - `HTTPServer` must stay single-threaded: `web_api.py` keeps its own SolarProvider/LunarProvider, which are not thread-safe.
 - Each TFT view has a JavaScript twin in `solar_clock/web/js/views/`. When you change a TFT view's text, format or colours, change its twin too and run `node --test tests/web/*.test.mjs`.
 - Preview without a display: `./venv/bin/python -m tools.web_preview --config config.example.json --sample-weather` (port 8091).
````

- [ ] **Step 2: Full checks**

```bash
./venv/bin/pytest -q
node --test tests/web/*.test.mjs
for tz in Asia/Tokyo UTC Pacific/Kiritimati; do TZ=$tz node --test tests/web/*.test.mjs 2>&1 | grep -E "^ℹ (pass|fail)" | tr '\n' ' '; echo "$tz"; done
./venv/bin/black --check solar_clock tests && ./venv/bin/flake8 solar_clock tests --max-line-length=100 --ignore=E501,W503 && ./venv/bin/mypy solar_clock --ignore-missing-imports --no-error-summary
./venv/bin/mypy --strict --ignore-missing-imports --follow-imports=silent solar_clock/web_api.py solar_clock/web_static.py tools/web_preview.py
<scratchpad>/ruffenv/bin/ruff check --no-cache --target-version py39 solar_clock/web_api.py tests/test_web_api.py tests/test_web_contract.py
./venv/bin/pre-commit run --all-files
```

Expected: Python `322 passed, 3 skipped`; JS 85 pass, and `ℹ pass 85 ℹ fail 0` for each of the three timezones; every linter and every pre-commit hook clean.

- [ ] **Step 3: TFT proof 1.** The files the TFT runs on are unchanged.

```bash
git diff --stat main -- solar_clock/views solar_clock/data solar_clock/display.py solar_clock/touch_handler.py solar_clock/main.py
```

Expected: prints nothing.

- [ ] **Step 4: TFT proof 2: pixel parity.** Render all 9 TFT views in both themes at `main` and at the branch head, with the time frozen and identical fixed data; every image must be identical. The two scripts are in the phase 1 plan (its Task 10, Step 5). They are deliberately not committed, so copy them out of that plan:

```bash
P=<scratchpad>/parity
mkdir -p "$P"
./venv/bin/python - "$P" <<'EOF'
import re, sys
from pathlib import Path

plan = Path("docs/superpowers/plans/2026-10-08-web-page-phase1.md").read_text()
for name in ("render_tft.py", "compare.py"):
    block = re.search(
        r"`<scratchpad>/parity/" + re.escape(name) + r"`:\n\n```python\n(.*?)\n```\n", plan, re.DOTALL
    )
    assert block, f"{name} not found in the phase 1 plan"
    Path(sys.argv[1], name).write_text(block.group(1) + "\n")
    print(name, len(block.group(1).splitlines()), "lines")
EOF
git worktree add "$P/base" main
./venv/bin/python -I "$P/render_tft.py" "$P/base" "$P/out-base"
./venv/bin/python -I "$P/render_tft.py" "$PWD" "$P/out-head"
./venv/bin/python -I "$P/compare.py" "$P/out-base" "$P/out-head"
git worktree remove "$P/base"
```

Expected: `render_tft.py 160 lines`, `compare.py 18 lines`, two `rendered 18 images` lines, then `18/18 identical`, exit 0. Any `DIFFERENT:` line means phase 2 changed the TFT. Stop and find out why before going further.

- [ ] **Step 5: Preview smoke test.** Check nothing is already listening on the port first (`ss -tlnp | grep :8091` must print nothing; never kill whatever is there, pick another port instead).

```bash
./venv/bin/python -m tools.web_preview --config config.example.json --sample-weather --bind 127.0.0.1 --port 8091 > <scratchpad>/preview.log 2>&1 &
echo $! > <scratchpad>/preview.pid
timeout 20 bash -c 'until curl -sf http://127.0.0.1:8091/health >/dev/null; do :; done'
for u in / /js/svg.js /js/views/sunpath.js /js/views/daylength.js /js/views/analemma.js /js/views/analogclock.js /api/now /api/charts /api/chart /screenshot; do
  curl -s -o /dev/null -w "$u %{http_code} %{content_type}\n" "http://127.0.0.1:8091$u"
done
curl -s -o /dev/null -w "/../config.json %{http_code}\n" --path-as-is "http://127.0.0.1:8091/../config.json"
kill "$(cat <scratchpad>/preview.pid)"
grep "Web page:" <scratchpad>/preview.log
```

Expected: the first eight paths answer 200 (`/api/charts` as `application/json`), `/api/chart` 404, `/screenshot` 503, `/../config.json` 404, and the log says `Web page: 24 files`.

- [ ] **Step 6: Peter's look on his phone (STOP and wait)**
- Start the preview on all interfaces: `./venv/bin/python -m tools.web_preview --config config.example.json --sample-weather --bind 0.0.0.0` (port 8091; background it and save the PID as in Step 5).
- Ask Peter to open `http://<homelab's address>:8091/` on his phone. Get the address with `hostname -I`, which changes, so read it each time.
- Ask him to check the four new views (Sun Path, Day Length, Analemma, Analog Clock) in portrait and landscape, in the day theme (restart the preview with `--theme day`) and the night theme, and that nothing is cut off or overlapping. Ask whether he wants the Analemma's "Sun early"/"Sun late" labels left as on the TFT or swapped ("For Peter" item 1).
- Fix what he reports in the owning task's files, re-run Step 2, and commit each fix with its own message.
- Stop the preview by PID when done.

- [ ] **Step 7: Commit the docs**

```bash
git add README.md CLAUDE.md
git commit -m "Document the web page's chart views" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Merge, push, deploy and check on clock.local (gated)

- [ ] **Step 1: Ask Peter for the go-ahead (STOP).** Summarise the branch: commits, test counts, the parity result and his phone check. Pushing to GitHub and restarting the clock both need his explicit yes. A one-word "go" has been ambiguous before: confirm it means "push and deploy".

- [ ] **Step 2: Capture the "before" state**

```bash
curl -s http://clock.local:8080/view                     # e.g. "sunpath (4/9)": note the view
curl -s -o <scratchpad>/before.png http://clock.local:8080/screenshot
ssh clock.local 'ps -o rss= -p "$(systemctl show -p MainPID --value solar-clock)"'   # KB
```

For reference, on 2026-10-11 at 23:37, twelve hours after phase 1's restart, the service used 61.7 MB with no swap and 0 restarts.

- [ ] **Step 3: Merge and push.** The pre-push hook runs every lint hook and pytest.

```bash
git switch main
git merge --ff-only web-page-phase2
git push origin main
```

If the session is not allowed to push (it was blocked during phase 1), ask Peter to type `! git push origin main` himself.

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
curl -s -o /dev/null -w "/api/charts %{http_code} %{content_type} %{size_download} bytes in %{time_total}s\n" http://clock.local:8080/api/charts
curl -s -o /dev/null -w "/api/charts again: %{time_total}s\n" http://clock.local:8080/api/charts
curl -s http://clock.local:8080/api/charts | python3 -c 'import json,sys; c=json.load(sys.stdin); print(c["date"], len(c["sun_path"]["elevations"]), len(c["day_length"]["points"]), len(c["analemma"]["points"]))'
curl -s -o /dev/null -w "/../config.json %{http_code}\n" --path-as-is "http://clock.local:8080/../config.json"
```

Expected:
- `active`, and a log line `Web page: 24 files from /home/pi/solar-clock/solar_clock/web`, with no `ERROR` or `Traceback`.
- `/` answers 200; `/api/charts` answers `200 application/json`, about 6 KB. Report how long the first request took (well under a second is expected) against the second, which comes from memory.
- The summary line prints today's date and `48 122 53`.
- `/../config.json` answers 404.

- [ ] **Step 6: Put the clock back on the view it showed, then compare.** A restart resets the clock to its default view.
- If Step 2 showed view *k* of 9 and the clock now shows view 1, call `curl -s http://clock.local:8080/next` *k - 1* times. That is the same as pressing the arrow on the clock, and it restores what Peter had on screen.
- Then run `curl -s -o <scratchpad>/after.png http://clock.local:8080/screenshot`.
- Look at `before.png` and `after.png`: apart from the time and live values, they must match.

- [ ] **Step 7: Memory, and Peter's checks**
- Record the RSS again now, and once more after about an hour with the page open on Peter's phone. Report both against Step 2.
- Ask Peter to:
  - swipe the physical screen once, to confirm touch still works;
  - open `http://clock.local:8080/` on his phone and flip through all nine views;
  - leave the Sun Path view open for a minute and confirm the sun's marker is where the TFT shows it.

- [ ] **Step 8: Wrap up**
- Phase 2, and with it the web page, is done when the checks above pass and Peter confirms.
- Delete the local branch `web-page-phase2` only if he agrees. Phase 1's leftovers (branches `web-page-phase1`, `web-page-phase1-build`, `worktree-web-page-phase1-build` and the worktree `.claude/worktrees/web-page-phase1-build`) also still wait for his OK.
