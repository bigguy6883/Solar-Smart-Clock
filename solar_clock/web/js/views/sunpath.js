// Sun Path view: mirrors solar_clock/views/sunpath.py.

import { countdownHM, escapeHtml, fixed, shortWeekdayDate, time12, zoned } from "../format.js";
import { n, scale } from "../svg.js";
import { namedColors } from "../theme.js";

export const name = "sunpath";
export const title = "Sun Path";

// The chart box, in SVG units. The scale is the TFT's: 40° on the top line and
// -90° on the bottom one. A summer sun climbs past 40° (on the TFT that part
// of the curve runs up into the header), so the picture grows upwards to fit.
const LEFT = 30;
const RIGHT = 350;
const TOP = 56;
const BOTTOM = 176;
const xAt = scale(0, 24 * 60, LEFT, RIGHT);
const yAt = scale(40, -90, TOP, BOTTOM);

export function render(data, now) {
  const colors = namedColors(data);
  const tz = data.location.timezone;
  return `<header class="view-header" style="background:${colors.ORANGE}"><h2>Sun Path</h2></header>
<div class="view-body">
  <p class="corners"><span>${time12(now, tz)}</span><span>${shortWeekdayDate(now, tz)}</span></p>
  ${chart(data, now, colors, tz)}
  <div class="row">
    ${eventPanel(data.sun, now, tz)}
    ${positionPanel(data.sun?.position)}
  </div>
</div>`;
}

function chart(data, now, colors, tz) {
  const path = data.charts?.sun_path;
  const position = data.sun?.position;
  const highest = Math.max(40, position?.elevation ?? 40, ...(path?.elevations ?? []));
  const top = Math.floor(yAt(highest)) - 10;
  const horizon = n(yAt(0));
  const hours = [0, 6, 12, 18, 24]
    .map((h) => `<text x="${n(xAt(h * 60))}" y="${BOTTOM + 14}" text-anchor="middle">${String(h).padStart(2, "0")}</text>`)
    .join("");
  return `<svg class="chart" viewBox="0 ${top} 360 ${BOTTOM + 20 - top}" role="img" aria-label="Sun elevation through the day">
    <text x="${LEFT - 4}" y="${TOP + 4}" text-anchor="end">40°</text>
    <text x="${LEFT - 4}" y="${n(yAt(0) + 4)}" text-anchor="end">0°</text>
    <text x="${LEFT - 4}" y="${BOTTOM - 2}" text-anchor="end">-90°</text>
    ${hours}
    <line class="axis" x1="${LEFT}" y1="${horizon}" x2="${RIGHT}" y2="${horizon}" stroke-width="2.5"/>
    ${curve(path, colors)}
    ${marker(position, now, tz)}
  </svg>`;
}

/** The day's curve: dark blue while the sun is down, the sun colour while it is up. */
function curve(path, colors) {
  if (!path) return "";
  const points = path.elevations.map((elevation, i) =>
    elevation === null ? null : { x: xAt(i * path.step_minutes), y: yAt(elevation), up: elevation >= 0 },
  );
  let down = "";
  let up = "";
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (a === null || b === null) continue;
    const piece = `M${n(a.x)} ${n(a.y)}L${n(b.x)} ${n(b.y)}`;
    if (a.up || b.up) up += piece;
    else down += piece;
  }
  return `<path d="${down}" fill="none" stroke="${colors.DARK_BLUE}" stroke-width="3" stroke-linecap="round"/>
    <path d="${up}" fill="none" style="stroke:var(--accent-sun)" stroke-width="3" stroke-linecap="round"/>`;
}

function marker(position, now, tz) {
  if (!position) return "";
  const z = zoned(now, tz);
  return `<circle cx="${n(xAt(z.hour * 60 + z.minute))}" cy="${n(yAt(position.elevation))}" r="6" style="fill:var(--accent-sun);stroke:var(--accent-warm)"/>`;
}

// Solar noon until it has passed, then whatever comes next.
function eventPanel(sun, now, tz) {
  let event = sun?.next_event ?? null;
  if (sun?.times?.noon && new Date(sun.times.noon) > now) event = { name: "Solar Noon", at: sun.times.noon };
  if (!event) return `<section class="panel"></section>`;
  const left = countdownHM(event.at, now);
  return `<section class="panel">
      <span class="warm">${escapeHtml(event.name)} <span class="primary">in ${left.h}h ${left.m}m</span></span>
      <span class="secondary">at ${time12(event.at, tz)}</span>
    </section>`;
}

function positionPanel(position) {
  const body = position
    ? `<span class="value sun">El ${fixed(position.elevation)}°</span><span class="secondary small">Az ${fixed(position.azimuth)}°</span>`
    : "";
  return `<section class="panel">${body}</section>`;
}
