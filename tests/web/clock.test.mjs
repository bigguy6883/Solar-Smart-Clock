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
