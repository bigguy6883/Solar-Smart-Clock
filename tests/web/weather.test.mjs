import { test } from "node:test";

import { render } from "../../solar_clock/web/js/views/weather.js";
import { NOW, assertShows, sampleNow } from "./fixtures.mjs";

test("weather view matches the TFT's text", () => {
  assertShows(render(sampleNow(), NOW), [
    "Weather", "64°F", "Feels 63°", "Humidity 58%", "Wind 7 WSW", "Scattered Clouds",
    "Today", "Tmrw", "Sat", "66°", "51°", '<td class="secondary">10%</td>',
    '<td class="cool">40%</td>', "Test City",
  ]);
});

test("without weather it shows the TFT message", () => {
  const data = sampleNow();
  data.weather = null;
  assertShows(render(data, NOW), ["Weather data unavailable", "Test City"]);
});
