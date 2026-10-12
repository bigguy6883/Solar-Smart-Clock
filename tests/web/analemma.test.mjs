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

test("the season labels move out of the way of a figure that reaches them", () => {
  const data = samplePage();
  data.charts.analemma.points = [
    { date: "2026-06-18", elevation: 88, equation_of_time: 0 }, // the tropics: far above the axis
    { date: "2026-12-24", elevation: 25.9, equation_of_time: 0 }, // 40°N in winter: below it
  ];
  assertShows(render(data, NOW), [
    'viewBox="0 -45 240 268"',
    '<text x="120" y="-35" text-anchor="middle" style="fill:var(--accent-sun)">Summer</text>',
    '<text x="120" y="217" text-anchor="middle" style="fill:var(--accent-cool)">winter</text>',
  ]);
});

test("a figure that fits leaves the labels where the TFT has them", () => {
  const fits = [
    'viewBox="0 0 240 212"',
    '<text x="120" y="10" text-anchor="middle" style="fill:var(--accent-sun)">Summer</text>',
    '<text x="120" y="206" text-anchor="middle" style="fill:var(--accent-cool)">winter</text>',
  ];
  const data = samplePage();
  data.charts.analemma.points = [
    { date: "2026-06-18", elevation: 70, equation_of_time: 0 },
    { date: "2026-12-24", elevation: 40, equation_of_time: 0 },
  ];
  assertShows(render(data, NOW), fits);
  data.charts = null; // still loading: nothing to dodge
  assertShows(render(data, NOW), fits);
});
