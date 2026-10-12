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
