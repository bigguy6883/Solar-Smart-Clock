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
