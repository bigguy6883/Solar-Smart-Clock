import { test } from "node:test";
import assert from "node:assert/strict";

import {
  aqiHeaderColor, aqiTextColor, cssVariables, namedColors, pollutantBarColor, timeOfDayHeader,
} from "../../solar_clock/web/js/theme.js";
import { NOW, TZ, sampleNow } from "./fixtures.mjs";

const data = sampleNow();
const colors = namedColors(data);
const at = (time) => new Date(`2026-10-08T${time}:00-04:00`);

test("header colour follows the sun like BaseView.get_time_header_color", () => {
  assert.equal(timeOfDayHeader(at("06:00"), data.sun, colors, TZ), colors.DARK_BLUE);
  assert.equal(timeOfDayHeader(at("06:50"), data.sun, colors, TZ), colors.ORANGE);
  assert.equal(timeOfDayHeader(NOW, data.sun, colors, TZ), colors.LIGHT_BLUE);
  assert.equal(timeOfDayHeader(at("18:45"), data.sun, colors, TZ), colors.ORANGE);
  assert.equal(timeOfDayHeader(at("21:00"), data.sun, colors, TZ), colors.PURPLE);
});

test("header colour falls back to fixed hours without sun data", () => {
  assert.equal(timeOfDayHeader(at("05:00"), null, colors, TZ), colors.DARK_BLUE);
  assert.equal(timeOfDayHeader(at("07:30"), null, colors, TZ), colors.ORANGE);
  assert.equal(timeOfDayHeader(at("16:59"), null, colors, TZ), colors.LIGHT_BLUE);
  assert.equal(timeOfDayHeader(at("19:00"), null, colors, TZ), colors.ORANGE);
  assert.equal(timeOfDayHeader(at("20:00"), null, colors, TZ), colors.PURPLE);
});

test("AQI colours match AirQualityView", () => {
  assert.equal(aqiHeaderColor(42, colors), "#00822d");
  assert.equal(aqiHeaderColor(250, colors), colors.AQI_VERY_UNHEALTHY);
  assert.equal(aqiTextColor(42, "night", colors), colors.AQI_GOOD);
  assert.equal(aqiTextColor(80, "night", colors), "#c8b400");
  assert.equal(aqiTextColor(80, "day", colors), "#aa8200");
  assert.equal(aqiTextColor(400, "night", colors), colors.AQI_HAZARDOUS);
});

test("pollutant bars change colour at half and three-quarters full", () => {
  assert.equal(pollutantBarColor(0.49, colors), colors.AQI_GOOD);
  assert.equal(pollutantBarColor(0.5, colors), colors.AQI_MODERATE);
  assert.equal(pollutantBarColor(0.75, colors), colors.AQI_UNHEALTHY);
});

test("palette keys become CSS variables", () => {
  const vars = new Map(cssVariables(data.theme.palettes.night));
  assert.equal(vars.get("--background-panel-dark"), "#191e19");
  assert.equal(vars.get("--accent-sun"), "#ffdc32");
  assert.equal(vars.size, 20);
});

test("only #rrggbb colours are accepted from the API", () => {
  const theme = { colors: { GOOD: "#00FF7f", QUOTE: 'red" onclick="alert(1)', SHORT: "#fff", NUMBER: 5 } };
  assert.deepEqual(namedColors({ theme }), { GOOD: "#00FF7f" });
  assert.deepEqual(namedColors({ theme: null }), {});
});
