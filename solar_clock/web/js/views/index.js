// Views in the same order as the TFT (solar_clock/views/__init__.py).

import * as airquality from "./airquality.js";
import * as analemma from "./analemma.js";
import * as analogclock from "./analogclock.js";
import * as clock from "./clock.js";
import * as daylength from "./daylength.js";
import * as moon from "./moon.js";
import * as solar from "./solar.js";
import * as sunpath from "./sunpath.js";
import * as weather from "./weather.js";

export const VIEWS = [
  clock, weather, airquality, sunpath, daylength, solar, moon, analemma, analogclock,
];
