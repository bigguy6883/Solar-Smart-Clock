// Day Length view: mirrors solar_clock/views/daylength.py.

import {
  addDays, dayLengthPadded, dayLengthText, daysBetween, escapeHtml, fixed, isoDate, shortDate,
} from "../format.js";
import { linePath, n, scale } from "../svg.js";
import { namedColors } from "../theme.js";

export const name = "daylength";
export const title = "Day Length";

// The chart box, in SVG units: 9 to 15 hours of daylight, as on the TFT.
const LEFT = 30;
const RIGHT = 350;
const TOP = 10;
const BOTTOM = 110;
const HALF_YEAR = 182;
const MONTHS = ["Ja", "F", "Mr", "Ap", "My", "Jn", "Jl", "Au", "S", "O", "N", "D"];
const xAt = scale(0, 365, LEFT, RIGHT);
const yAt = scale(9, 15, BOTTOM, TOP);

export function render(data, now) {
  const colors = namedColors(data);
  const today = isoDate(now, data.location.timezone);
  const yearly = data.charts?.day_length;
  return `<header class="view-header" style="background:${colors.ORANGE}"><h2>Day Length</h2></header>
<div class="view-body">
  ${chart(yearly, data.sun, today, colors)}
  <div class="row">
    ${todayPanel(data.sun)}
    ${extremesPanel(yearly)}
    ${nextPanel(yearly, today)}
  </div>
</div>`;
}

// The year is turned so that today sits in the middle of the chart.
function chart(yearly, sun, today, colors) {
  const hourLabels = [14, 12, 10]
    .map((h) => `<text x="${LEFT - 4}" y="${n(yAt(h) + 4)}" text-anchor="end">${h}h</text>`)
    .join("");
  const firstMonth = Number(addDays(today, -HALF_YEAR).slice(5, 7)) - 1;
  const monthLabels = MONTHS.map((_, i) =>
    `<text x="${n(xAt((i / 12) * 365))}" y="${BOTTOM + 14}">${MONTHS[(firstMonth + i) % 12]}</text>`,
  ).join("");
  return `<svg class="chart" viewBox="0 0 360 128" role="img" aria-label="Day length through the year">
    ${hourLabels}
    ${monthLabels}
    ${curve(yearly, today, colors)}
    ${todayDot(sun)}
  </svg>`;
}

function curve(yearly, today, colors) {
  if (!yearly) return "";
  const shift = daysBetween(`${today.slice(0, 4)}-01-01`, today) - HALF_YEAR;
  const points = yearly.points
    .map(([day, hours]) => [
      xAt((((day - shift) % 365) + 365) % 365),
      Math.max(TOP, Math.min(BOTTOM, yAt(hours))),
    ])
    .sort((a, b) => a[0] - b[0]);
  return `<path d="${linePath(points)}" fill="none" stroke="${colors.ORANGE}" stroke-width="1.5"/>`;
}

function todayDot(sun) {
  if (!sun?.day_length_hours) return "";
  return `<circle cx="${(LEFT + RIGHT) / 2}" cy="${n(yAt(sun.day_length_hours))}" r="4" style="fill:var(--text-primary);stroke:var(--accent-sun)"/>`;
}

function todayPanel(sun) {
  const length = sun?.day_length_hours
    ? `<span class="value">${dayLengthText(sun.day_length_hours)}</span>`
    : "";
  const change = sun?.day_length_change_min;
  const changeText = change
    ? `<span class="small ${change > 0 ? "sun" : "cool"}">${change > 0 ? "+" : ""}${fixed(change, 1)}m/day</span>`
    : "";
  return `<section class="panel"><span class="label">Today</span>${length}${changeText}</section>`;
}

function extremesPanel(yearly) {
  const column = (label, day, tone) => {
    const hours = day && day.hours !== null ? `<span class="${tone} nowrap">${dayLengthPadded(day.hours)}</span>` : "";
    const date = day ? `<span class="secondary small">${shortDate(day.date)}</span>` : "";
    return `<div class="stat"><span class="label small">${label}</span>${hours}${date}</div>`;
  };
  return `<section class="panel pair">
      ${column("Shortest", yearly?.shortest, "cool")}
      ${column("Longest", yearly?.longest, "warm")}
    </section>`;
}

// The next solstice or equinox this year; after the winter solstice the box is empty.
function nextPanel(yearly, today) {
  const next = yearly?.events.find((event) => daysBetween(today, event.date) > 0);
  const body = next
    ? `<div class="pair">
        <div class="stat"><span class="green">${escapeHtml(next.name)}</span><span class="secondary small">${shortDate(next.date)}</span></div>
        <div class="stat"><span class="value">${daysBetween(today, next.date)}</span><span class="label small">days</span></div>
      </div>`
    : "";
  return `<section class="panel"><span class="label">Next</span>${body}</section>`;
}
