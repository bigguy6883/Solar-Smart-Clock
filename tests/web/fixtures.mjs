// A realistic /api/now response for the view tests: Thursday 8 Oct 2026,
// 3:12 PM in New York, night theme. Edit copies, never this object.

import assert from "node:assert/strict";

export const TZ = "America/New_York";
export const NOW = new Date("2026-10-08T15:12:00-04:00");

const SAMPLE = {
  generated_at: "2026-10-08T15:12:00-04:00",
  location: { name: "Test City", timezone: TZ },
  units: "imperial",
  theme: {
    mode: "auto",
    active: "night",
    palettes: {
      day: {
        background: "#f5f3eb", background_panel: "#e6e4dc", background_panel_dark: "#dcdad2",
        text_primary: "#1e1e1e", text_secondary: "#505050", text_tertiary: "#787878",
        nav_background: "#ebe9e1", nav_button: "#c8c6be", nav_dot_active: "#1e1e1e",
        nav_dot_inactive: "#a0a0a0", clock_face: "#fffffa", clock_hands: "#1e1e1e",
        clock_markers: "#505050", divider: "#c8c6be", outline: "#b4b2aa",
        accent_sun: "#a06400", accent_warm: "#b44600", accent_moon: "#7d5f0a",
        accent_cool: "#1e5ab4", accent_green: "#147328",
      },
      night: {
        background: "#000000", background_panel: "#232328", background_panel_dark: "#191e19",
        text_primary: "#ffffff", text_secondary: "#b4b4b4", text_tertiary: "#808080",
        nav_background: "#000000", nav_button: "#3c3c3c", nav_dot_active: "#ffffff",
        nav_dot_inactive: "#808080", clock_face: "#f0f0e6", clock_hands: "#000000",
        clock_markers: "#323232", divider: "#282832", outline: "#808080",
        accent_sun: "#ffdc32", accent_warm: "#ff961e", accent_moon: "#fff8dc",
        accent_cool: "#6495ed", accent_green: "#00c800",
      },
    },
    colors: {
      BLACK: "#000000", WHITE: "#ffffff", YELLOW: "#ffdc32", ORANGE: "#ff8c00",
      BLUE: "#6495ed", DARK_BLUE: "#191970", LIGHT_BLUE: "#87ceeb", GRAY: "#808080",
      LIGHT_GRAY: "#b4b4b4", DARK_GRAY: "#323232", RED: "#ff5050", PURPLE: "#9370db",
      GREEN: "#00c800", MOON_YELLOW: "#fff8dc", AQI_GOOD: "#00e400", AQI_MODERATE: "#ffff00",
      AQI_UNHEALTHY_SENSITIVE: "#ff7e00", AQI_UNHEALTHY: "#ff0000",
      AQI_VERY_UNHEALTHY: "#8f3f97", AQI_HAZARDOUS: "#7e0023",
      NAV_BUTTON_COLOR: "#3c3c3c", NAV_BUTTON_ACTIVE: "#505050",
    },
  },
  sun: {
    times: {
      dawn: "2026-10-08T06:42:00-04:00",
      sunrise: "2026-10-08T07:08:00-04:00",
      noon: "2026-10-08T12:52:00-04:00",
      sunset: "2026-10-08T18:35:00-04:00",
      dusk: "2026-10-08T19:01:00-04:00",
    },
    golden_hour: {
      morning: { start: "2026-10-08T06:52:00-04:00", end: "2026-10-08T07:47:00-04:00" },
      evening: { start: "2026-10-08T17:56:00-04:00", end: "2026-10-08T18:51:00-04:00" },
    },
    position: { elevation: 31.42, azimuth: 222.6 },
    day_length_hours: 11.5,
    day_length_change_min: -2.13,
    next_event: { name: "Sunset", at: "2026-10-08T18:35:00-04:00" },
    next_main_event: { name: "Sunset", at: "2026-10-08T18:35:00-04:00" },
  },
  weather: {
    current: {
      temperature: 64.5, feels_like: 63.2, humidity: 58,
      description: "Scattered Clouds", wind_speed: 7.4, wind_direction: "WSW",
    },
    forecast: [
      { date: "2026-10-08", high_temp: 66.1, low_temp: 51.3, rain_chance: 10 },
      { date: "2026-10-09", high_temp: 61.0, low_temp: 48.8, rain_chance: 40 },
      { date: "2026-10-10", high_temp: 58.4, low_temp: 45.0, rain_chance: 0 },
    ],
  },
  air_quality: {
    aqi: 42, category: "Good", pm25: 10.1, pm10: 18.4, o3: 61.2, no2: 12.7, so2: 1.9,
    co: 230.5, updated_at: "2026-10-08T14:58:00-04:00",
  },
  moon: {
    phase: {
      phase: 0.89, illumination: 14.2, phase_name: "Waning Crescent",
      next_new: "2026-10-10", next_full: "2026-10-26", days_to_new: 2, days_to_full: 18,
    },
    times: { moonrise: "2026-10-08T03:41:00-04:00", moonset: "2026-10-08T17:20:00-04:00" },
  },
};

/** A fresh copy of the sample, safe to modify in a test. */
export function sampleNow() {
  return structuredClone(SAMPLE);
}

const DAY_MS = 86_400_000;
const TURN = 2 * Math.PI;
const round = (value, digits) => Number(value.toFixed(digits));
const dayOf2026 = (day) => new Date(Date.UTC(2026, 0, 1) + day * DAY_MS).toISOString().slice(0, 10);

/** The equation of time in minutes for a day of the year (textbook approximation). */
function equationOfTime(day) {
  const b = (TURN * (day - 81)) / 364;
  return 9.87 * Math.sin(2 * b) - 7.53 * Math.cos(b) - 1.5 * Math.sin(b);
}

// A /api/charts response for the same day. The curves are smooth stand-ins
// with the real shapes and sizes (48, 122 and 53 samples), not real astronomy;
// tests/test_web_contract.py feeds the views the real thing.
const CHARTS = {
  date: "2026-10-08",
  sun_path: {
    step_minutes: 30,
    // Highest (43°) at 12:45 PM, lowest (-55°) at 12:45 AM.
    elevations: Array.from({ length: 48 }, (_, i) =>
      round(-6 + 49 * Math.cos((TURN * (i * 30 - 765)) / 1440), 2)),
  },
  day_length: {
    year: 2026,
    points: Array.from({ length: 122 }, (_, i) =>
      [i * 3, round(12.17 + 2.92 * Math.sin((TURN * (i * 3 - 80)) / 365), 3)]),
    shortest: { date: "2026-12-21", hours: 9.245021295277779 },
    longest: { date: "2026-06-21", hours: 15.086548289166666 },
    events: [
      { name: "Vernal", date: "2026-03-20" },
      { name: "Summer", date: "2026-06-21" },
      { name: "Autumn", date: "2026-09-23" },
      { name: "Winter", date: "2026-12-21" },
    ],
  },
  analemma: {
    points: Array.from({ length: 53 }, (_, week) => ({
      date: dayOf2026(week * 7),
      elevation: round(49.3 + 23.4 * Math.sin((TURN * (week * 7 - 80)) / 365), 2),
      equation_of_time: round(equationOfTime(week * 7), 2),
    })),
    equation_of_time: 12.733333333333348,
  },
};

/** A fresh copy of the sample charts, safe to modify in a test. */
export function sampleCharts() {
  return structuredClone(CHARTS);
}

/** What app.js hands a view: the /api/now sample with the charts attached. */
export function samplePage() {
  return { ...sampleNow(), charts: sampleCharts() };
}

/** Every string that must never reach the page unescaped. */
export const HOSTILE = '<img src=x onerror="alert(1)">';

/** Fail unless every string in `expected` appears in `html`. */
export function assertShows(html, expected) {
  for (const text of expected) assert.ok(html.includes(text), `missing: ${text}`);
}
