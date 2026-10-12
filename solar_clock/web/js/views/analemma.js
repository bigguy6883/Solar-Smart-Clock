// Analemma view: mirrors solar_clock/views/analemma.py.

import { daysBetween, fixed, isoDate } from "../format.js";
import { n } from "../svg.js";
import { namedColors } from "../theme.js";

export const name = "analemma";
export const title = "Analemma";

// The TFT's diagram, in its own pixel coordinates: 15 minutes of equation of
// time is 50 units across, and 47° of noon elevation around 55° is 170 units.
const CX = 120;
const CY = 95;
const xAt = (minutes) => CX + (minutes / 15) * 50;
const yAt = (elevation) => CY - ((elevation - 55) / 47) * 170;

const SEASONS = [
  ["Sp", "spring", "var(--accent-green)"],
  ["Su", "summer", "var(--accent-sun)"],
  ["Fa", "fall", "var(--accent-warm)"],
  ["Wi", "winter", "var(--accent-cool)"],
];

function seasonColor(isoDay) {
  const month = Number(isoDay.slice(5, 7));
  const index = month >= 3 && month <= 5 ? 0 : month >= 6 && month <= 8 ? 1 : month >= 9 && month <= 11 ? 2 : 3;
  return SEASONS[index][2];
}

export function render(data, now) {
  const colors = namedColors(data);
  const today = isoDate(now, data.location.timezone);
  const charts = data.charts;
  return `<header class="view-header" style="background:${colors.ORANGE}"><h2>Analemma</h2></header>
<div class="view-body">
  <div class="row wide">
    ${diagram(charts, today)}
    <div class="analemma-info">
      ${todayPanel(charts?.analemma)}
      ${sunPathPanel(data.sun?.position)}
      ${legend()}
    </div>
  </div>
</div>`;
}

function diagram(charts, today) {
  const points = charts?.analemma?.points ?? [];
  // No answer yet draws the bare axes; an answer without analemma data says so.
  const body = charts && !charts.analemma
    ? `<text class="chart-message" x="${CX}" y="${CY - 30}" text-anchor="middle">Data unavailable</text>`
    : dots(points, today);
  // The TFT prints the season labels at fixed heights, where a figure that
  // reaches them is drawn over them. Here they move clear of it instead, and
  // the picture grows to fit.
  const heights = points.map((point) => yAt(point.elevation)).filter(Number.isFinite);
  const summerY = Math.min(10, Math.floor(Math.min(...heights)) - 10);
  const winterY = Math.max(206, Math.ceil(Math.max(...heights)) + 16);
  const top = summerY - 10;
  return `<svg class="chart analemma-chart" viewBox="0 ${n(top)} 240 ${n(winterY + 6 - top)}" role="img" aria-label="Analemma: the noon sun through the year">
      <text x="${CX}" y="${n(summerY)}" text-anchor="middle" style="fill:var(--accent-sun)">Summer</text>
      <text x="${CX}" y="${n(winterY)}" text-anchor="middle" style="fill:var(--accent-cool)">winter</text>
      <text x="5" y="${CY - 4}">Sun</text><text x="5" y="${CY + 16}">early</text>
      <text x="235" y="${CY - 4}" text-anchor="end">Sun</text><text x="235" y="${CY + 16}" text-anchor="end">late</text>
      <line class="axis" x1="${CX}" y1="20" x2="${CX}" y2="190"/>
      <line class="axis" x1="30" y1="${CY}" x2="210" y2="${CY}"/>
      ${body}
    </svg>`;
}

function dots(points, today) {
  let nearest = null;
  const circles = points.map((point) => {
    // As on the TFT, the last sample within a week of today is "today".
    if (Math.abs(daysBetween(point.date, today)) < 7) nearest = point;
    return `<circle cx="${n(xAt(point.equation_of_time))}" cy="${n(yAt(point.elevation))}" r="2" style="fill:${seasonColor(point.date)}"/>`;
  });
  const todayDot = nearest
    ? `<circle cx="${n(xAt(nearest.equation_of_time))}" cy="${n(yAt(nearest.elevation))}" r="6" style="fill:var(--text-primary);stroke:var(--accent-sun)"/>`
    : "";
  return circles.join("") + todayDot;
}

function todayPanel(analemma) {
  const minutes = analemma?.equation_of_time;
  const body = minutes
    ? `<span class="label">Sun is</span><span class="value big sun">${fixed(Math.abs(minutes), 1)} min</span><span class="secondary">${minutes > 0 ? "early" : "late"}</span>`
    : "";
  return `<section class="panel boxed"><h3 class="panel-title">Today</h3>${body}</section>`;
}

function sunPathPanel(position) {
  const body = position
    ? `<span class="value big sun">${position.elevation > 45 ? "high" : "low"}</span><span class="secondary">${fixed(position.elevation, 1)}° S</span>`
    : "";
  return `<section class="panel boxed"><h3 class="panel-title">Sun path</h3>${body}</section>`;
}

function legend() {
  const items = SEASONS.map(
    ([label, , color]) => `<span class="legend-item"><span class="legend-dot" style="background:${color}"></span>${label}</span>`,
  ).join("");
  return `<p class="legend"><span class="label small">Legend:</span>${items}</p>`;
}
