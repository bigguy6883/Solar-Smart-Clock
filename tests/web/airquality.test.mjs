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
