import { test } from "node:test";
import assert from "node:assert/strict";

import { VIEWS } from "../../solar_clock/web/js/views/index.js";
import { HOSTILE, NOW, samplePage } from "./fixtures.mjs";

test("views come in TFT order and each has a name, title and render()", () => {
  assert.deepEqual(VIEWS.map((v) => v.name), [
    "clock", "weather", "airquality", "sunpath", "daylength", "solar", "moon",
  ]);
  for (const view of VIEWS) {
    assert.equal(typeof view.title, "string");
    assert.equal(typeof view.render(samplePage(), NOW), "string");
  }
});

test("every view renders when every data section is null", () => {
  const empty = samplePage();
  for (const key of ["theme", "sun", "weather", "air_quality", "moon", "charts"]) empty[key] = null;
  for (const view of VIEWS) assert.equal(typeof view.render(empty, NOW), "string", view.name);
});

test("every view renders when the charts arrived but each chart is null", () => {
  const data = samplePage();
  for (const key of ["sun_path", "day_length", "analemma"]) data.charts[key] = null;
  for (const view of VIEWS) {
    const html = view.render(data, NOW);
    assert.ok(!html.includes("undefined") && !html.includes("NaN"), view.name);
  }
});

test("text from the API is escaped in every view", () => {
  const data = samplePage();
  data.location.name = HOSTILE;
  data.weather.current.description = HOSTILE;
  data.weather.current.wind_direction = HOSTILE;
  data.air_quality.category = HOSTILE;
  data.sun.next_event.name = HOSTILE;
  data.moon.phase.phase_name = HOSTILE;
  for (const event of data.charts.day_length.events) event.name = HOSTILE;
  for (const view of VIEWS) {
    assert.ok(!view.render(data, NOW).includes("<img"), `${view.name} let markup through`);
  }
});

test("numbers and colours from the API can't carry markup either", () => {
  const data = samplePage();
  for (const key of Object.keys(data.theme.colors)) data.theme.colors[key] = HOSTILE;
  data.weather.current.humidity = HOSTILE;
  for (const day of data.weather.forecast) day.rain_chance = HOSTILE;
  data.air_quality.aqi = HOSTILE;
  data.moon.phase.days_to_new = HOSTILE;
  data.moon.phase.days_to_full = HOSTILE;
  data.charts.sun_path.step_minutes = HOSTILE;
  data.charts.sun_path.elevations = data.charts.sun_path.elevations.map(() => HOSTILE);
  data.charts.day_length.points = data.charts.day_length.points.map(() => [HOSTILE, HOSTILE]);
  for (const point of data.charts.analemma.points) {
    point.elevation = HOSTILE;
    point.equation_of_time = HOSTILE;
  }
  for (const view of VIEWS) {
    assert.ok(!view.render(data, NOW).includes("<img"), `${view.name} let markup through`);
  }
});
