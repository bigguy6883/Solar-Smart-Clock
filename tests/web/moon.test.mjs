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

test("new and full moons keep MoonView's rules", () => {
  assert.match(moonShadow(0.01), /<circle/); // new moon: fully dark
  assert.equal(moonShadow(0.5), ""); // full moon: no shadow
});

test("the shadow is bounded by the moon's own edge and the terminator", () => {
  // First quarter: exactly the left half of the disc.
  assert.equal(moonShadow(0.25), '<path d="M55 5A50 50 0 0 0 55 105A0 50 0 0 0 55 5Z" fill="#1e1e1e"/>');
  // Waxing crescent: left edge, terminator bulging right, into the lit side.
  assert.equal(moonShadow(0.1), '<path d="M55 5A50 50 0 0 0 55 105A40.45 50 0 0 0 55 5Z" fill="#1e1e1e"/>');
  // Waxing gibbous: left edge, terminator bulging left.
  assert.equal(moonShadow(0.4), '<path d="M55 5A50 50 0 0 0 55 105A40.45 50 0 0 1 55 5Z" fill="#1e1e1e"/>');
  // Waning gibbous: right edge, terminator bulging right.
  assert.equal(moonShadow(0.6), '<path d="M55 5A50 50 0 0 1 55 105A40.45 50 0 0 0 55 5Z" fill="#1e1e1e"/>');
  // Waning crescent: right edge, terminator bulging left.
  assert.equal(moonShadow(0.9), '<path d="M55 5A50 50 0 0 1 55 105A40.45 50 0 0 1 55 5Z" fill="#1e1e1e"/>');
});
