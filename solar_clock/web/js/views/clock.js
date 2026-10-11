// Clock view: mirrors solar_clock/views/clock.py.

import {
  clockParts, compass8, countdownHM, dayFraction, dayLengthPadded, escapeHtml, fixed,
  longDate, time12,
} from "../format.js";
import { namedColors, timeOfDayHeader } from "../theme.js";

export const name = "clock";
export const title = "Clock";

export function render(data, now) {
  const tz = data.location.timezone;
  const { time, ampm } = clockParts(now, tz);
  const header = timeOfDayHeader(now, data.sun, namedColors(data), tz);
  return `<header class="view-header clock-header" style="background:${header}">
  <span class="clock-time">${time}</span><span class="clock-ampm">${ampm}</span>
</header>
<div class="view-body">
  <p class="clock-date">${longDate(now, tz)}</p>
  ${sunRow(data.sun, tz)}
  ${weatherRow(data)}
  ${progress(data.sun, now, tz)}
</div>`;
}

function sunRow(sun, tz) {
  if (!sun) return "";
  const daylight = sun.day_length_hours
    ? `<span class="label">daylight</span><span class="value">${dayLengthPadded(sun.day_length_hours)}</span>`
    : "";
  return `<div class="sun-row">
    <div><span class="label">Sunrise</span><span class="value sun">${time12(sun.times.sunrise, tz)}</span></div>
    <div class="center">${daylight}</div>
    <div class="right"><span class="label">Sunset</span><span class="value warm">${time12(sun.times.sunset, tz)}</span></div>
  </div>`;
}

// As on the TFT, sun position is only shown alongside the weather.
function weatherRow(data) {
  const current = data.weather?.current;
  if (!current) return `<p class="secondary">Weather: unavailable</p>`;
  const unit = data.units === "metric" ? "°C" : "°F";
  return `<div class="row">
    <section class="panel">
      <span class="value">${escapeHtml(current.description)}</span>
      <span class="sun">Temp: ${fixed(current.temperature)}${unit}</span>
      <span class="secondary">Humidity: ${current.humidity}%</span>
    </section>
    ${sunPosition(data.sun?.position)}
  </div>`;
}

function sunPosition(position) {
  if (!position) return "";
  const arrow = position.elevation >= 0 ? "↑" : "↓";
  const tone = position.elevation > 0 ? "sun" : "warm";
  return `<section class="panel">
      <span class="label">Sun Position</span>
      <span class="${tone}">El: ${fixed(Math.abs(position.elevation))}° ${arrow}</span>
      <span class="secondary">Az: ${fixed(position.azimuth)}° ${compass8(position.azimuth)}</span>
    </section>`;
}

function progress(sun, now, tz) {
  const fraction = dayFraction(now, tz);
  const next = sun?.next_event;
  const left = next ? countdownHM(next.at, now) : null;
  const countdown = left ? `<p>${escapeHtml(next.name)} in ${left.h}h ${left.m}m</p>` : "";
  return `<div class="progress">
    <div class="bar"><div class="bar-fill" style="width:${(fraction * 100).toFixed(2)}%"></div></div>
    <p class="secondary">${fixed(fraction * 100)}% of day</p>
    ${countdown}
  </div>`;
}
