import { test } from "node:test";

import { render } from "../../solar_clock/web/js/views/solar.js";
import { NOW, assertShows, sampleNow } from "./fixtures.mjs";

test("solar view matches the TFT's text", () => {
  assertShows(render(sampleNow(), NOW), [
    "Dawn", "6:42 AM", "Solar Noon", "12:52 PM", "Dusk", "7:01 PM",
    "6:52 - 7:47 AM", "5:56 - 6:51 PM", "El: 31.4°", "Az: 223°", "11h 30m",
    "-2.1m vs yday", "color:#9370db", "Sunset", "in 3h 23m",
  ]);
});

test("without sun data it shows the TFT message", () => {
  const data = sampleNow();
  data.sun = null;
  assertShows(render(data, NOW), ["Solar data unavailable"]);
});
