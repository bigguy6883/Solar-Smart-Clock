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
