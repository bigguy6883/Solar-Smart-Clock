import { test } from "node:test";
import assert from "node:assert/strict";

import { VIEWS } from "../../solar_clock/web/js/views/index.js";
import { HOSTILE, NOW, sampleNow } from "./fixtures.mjs";

test("views come in TFT order and each has a name, title and render()", () => {
  assert.deepEqual(VIEWS.map((v) => v.name), ["clock"]);
  for (const view of VIEWS) {
    assert.equal(typeof view.title, "string");
    assert.equal(typeof view.render(sampleNow(), NOW), "string");
  }
});

test("every view renders when every data section is null", () => {
  const empty = sampleNow();
  for (const key of ["theme", "sun", "weather", "air_quality", "moon"]) empty[key] = null;
  for (const view of VIEWS) assert.equal(typeof view.render(empty, NOW), "string", view.name);
});

test("text from the API is escaped in every view", () => {
  const data = sampleNow();
  data.location.name = HOSTILE;
  data.weather.current.description = HOSTILE;
  data.weather.current.wind_direction = HOSTILE;
  data.air_quality.category = HOSTILE;
  data.sun.next_event.name = HOSTILE;
  data.moon.phase.phase_name = HOSTILE;
  for (const view of VIEWS) {
    assert.ok(!view.render(data, NOW).includes("<img"), `${view.name} let markup through`);
  }
});
