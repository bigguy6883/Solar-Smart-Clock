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
