import { test } from "node:test";
import assert from "node:assert/strict";

import {
  clockParts, compass8, countdownHM, dayFraction, dayLengthPadded, dayLengthText,
  escapeHtml, fixed, longDate, shortDate, time12, time12Bare, weekdayShort, zoned,
} from "../../solar_clock/web/js/format.js";
import { NOW, TZ } from "./fixtures.mjs";

test("times are shown in the clock's timezone, not the viewer's", () => {
  assert.equal(time12("2026-10-08T07:08:00-04:00", TZ), "7:08 AM");
  assert.equal(time12("2026-10-08T07:08:00-04:00", "Asia/Tokyo"), "8:08 PM");
  assert.equal(zoned(NOW, TZ).hour, 15);
});

test("12-hour times match %-I:%M %p, including midnight and noon", () => {
  assert.equal(time12("2026-10-08T00:05:00-04:00", TZ), "12:05 AM");
  assert.equal(time12("2026-10-08T12:00:00-04:00", TZ), "12:00 PM");
  assert.equal(time12("2026-10-08T18:35:00-04:00", TZ), "6:35 PM");
  assert.equal(time12Bare("2026-10-08T17:56:00-04:00", TZ), "5:56");
});

test("clock header and long date match the TFT", () => {
  assert.deepEqual(clockParts(NOW, TZ), { time: "3:12:00", ampm: "PM" });
  assert.equal(longDate(NOW, TZ), "Thursday, October 08, 2026");
});

test("date-only strings format without timezone shifts", () => {
  assert.equal(shortDate("2026-10-10"), "Oct 10");
  assert.equal(shortDate("2026-01-06"), "Jan 06");
  assert.equal(weekdayShort("2026-10-10"), "Sat");
});

test("day lengths truncate minutes like Python int()", () => {
  assert.equal(dayLengthPadded(11.5), "11h 30m");
  assert.equal(dayLengthPadded(9.0834), "9h 05m");
  assert.equal(dayLengthText(9.0834), "9h 5m");
});

test("countdown is hours and minutes and stops at zero", () => {
  assert.deepEqual(countdownHM("2026-10-08T18:35:00-04:00", NOW), { h: 3, m: 23 });
  assert.deepEqual(countdownHM("2026-10-08T15:00:00-04:00", NOW), { h: 0, m: 0 });
});

test("day fraction uses the clock's local midnight", () => {
  assert.equal(fixed(dayFraction(NOW, TZ) * 100), "63");
});

test("compass names match ClockView", () => {
  assert.equal(compass8(0), "N");
  assert.equal(compass8(222.6), "SW");
  assert.equal(compass8(337.5), "N");
  assert.equal(compass8(300), "NW");
});

test("fixed() rounds like Python format()", () => {
  const cases = [
    [64.5, 0, "64"], [65.5, 0, "66"], [2.25, 1, "2.2"], [2.75, 1, "2.8"],
    [0.15, 1, "0.1"], [-2.5, 0, "-2"], [-0.4, 0, "-0"], [-0.04, 1, "-0.0"],
    [31.42, 1, "31.4"], [222.6, 0, "223"],
  ];
  for (const [value, digits, expected] of cases) {
    assert.equal(fixed(value, digits), expected, `fixed(${value}, ${digits})`);
  }
});

test("escapeHtml neutralises markup", () => {
  assert.equal(escapeHtml(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
});
