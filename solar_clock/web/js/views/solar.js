// Solar Details view: mirrors solar_clock/views/solar.py.

import { countdownHM, dayLengthText, escapeHtml, fixed, time12, time12Bare } from "../format.js";
import { namedColors } from "../theme.js";

export const name = "solar";
export const title = "Solar Details";

export function render(data, now) {
  const colors = namedColors(data);
  const header = `<header class="view-header" style="background:${colors.ORANGE}"><h2>Solar Details</h2></header>`;
  const sun = data.sun;
  if (!sun) return `${header}<div class="view-body"><p class="message">Solar data unavailable</p></div>`;
  const tz = data.location.timezone;
  const t = sun.times;
  return `${header}
<div class="view-body">
  <div class="times-grid">
    <div>${event("Dawn", t.dawn, "secondary", tz)}${event("Sunrise", t.sunrise, "sun", tz)}${event("Solar Noon", t.noon, "secondary", tz)}</div>
    <div>${event("Sunset", t.sunset, "sun", tz)}${event("Dusk", t.dusk, "warm", tz)}</div>
  </div>
  ${goldenHour(sun.golden_hour, tz)}
  <div class="row">
    ${positionPanel(sun.position)}
    ${dayLengthPanel(sun, colors)}
    ${nextEventPanel(sun.next_event, now)}
  </div>
</div>`;
}

function event(label, at, tone, tz) {
  return `<div class="stat"><span class="label">${label}</span><span class="value ${tone}">${time12(at, tz)}</span></div>`;
}

function goldenHour(golden, tz) {
  const range = (span) => `${time12Bare(span.start, tz)} - ${time12(span.end, tz)}`;
  const morning = golden.morning
    ? `<p class="golden-row"><span class="label">Morning:</span> <span class="sun">${range(golden.morning)}</span></p>`
    : "";
  const evening = golden.evening
    ? `<p class="golden-row"><span class="label">Evening:</span> <span class="warm">${range(golden.evening)}</span></p>`
    : "";
  return `<section class="golden"><h3>Golden Hour</h3>${morning}${evening}</section>`;
}

function positionPanel(position) {
  const body = position
    ? `<span class="value sun">El: ${fixed(position.elevation, 1)}°</span><span class="secondary small">Az: ${fixed(position.azimuth)}°</span>`
    : "";
  return `<section class="panel"><span class="label">Sun Position</span>${body}</section>`;
}

function dayLengthPanel(sun, colors) {
  const length = sun.day_length_hours
    ? `<span class="value">${dayLengthText(sun.day_length_hours)}</span>`
    : "";
  const change = sun.day_length_change_min;
  const changeText = change
    ? `<span class="small" style="color:${change > 0 ? "var(--accent-sun)" : colors.PURPLE}">${change > 0 ? "+" : ""}${fixed(change, 1)}m vs yday</span>`
    : "";
  return `<section class="panel"><span class="label">Day Length</span>${length}${changeText}</section>`;
}

function nextEventPanel(next, now) {
  const left = next ? countdownHM(next.at, now) : null;
  const body = left
    ? `<span class="value warm">${escapeHtml(next.name)}</span><span class="secondary small">in ${left.h}h ${left.m}m</span>`
    : "";
  return `<section class="panel"><span class="label">Next Event</span>${body}</section>`;
}
