// Analog Clock view: mirrors solar_clock/views/analogclock.py.

import { weekdayDate, zoned } from "../format.js";
import { n } from "../svg.js";
import { namedColors, timeOfDayHeader } from "../theme.js";

export const name = "analogclock";
export const title = "Analog Clock";

const C = 110; // face centre in a 220 x 220 viewBox
const R = 100; // face radius, as on the TFT
const SECOND_HAND = "#c80000"; // (200, 0, 0), the TFT's second hand

/** The point `radius` out from the centre, `degrees` clockwise from 12 o'clock. */
function point(degrees, radius) {
  const angle = ((degrees - 90) * Math.PI) / 180;
  return [n(C + radius * Math.cos(angle)), n(C + radius * Math.sin(angle))];
}

function spoke(degrees, from, to, attributes) {
  const [x1, y1] = point(degrees, from);
  const [x2, y2] = point(degrees, to);
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${attributes}/>`;
}

export function render(data, now) {
  const tz = data.location.timezone;
  const background = timeOfDayHeader(now, data.sun, namedColors(data), tz);
  return `<div class="analog" style="background:${background}">
  <span class="analog-title">Analog</span>
  ${face(zoned(now, tz))}
  <p class="analog-date">${weekdayDate(now, tz)}</p>
</div>`;
}

function face(z) {
  return `<svg class="analog-face" viewBox="0 0 220 220" role="img" aria-label="Analog clock">
    <circle cx="${C}" cy="${C}" r="${R + 5}" stroke-width="3" style="fill:var(--clock-face);stroke:var(--outline)"/>
    ${markers()}
    ${hands(z)}
    <circle cx="${C}" cy="${C}" r="6" style="fill:var(--clock-hands)"/>
    <circle cx="${C}" cy="${C}" r="3" fill="${SECOND_HAND}"/>
  </svg>`;
}

// Long marks at 12, 3, 6 and 9; a thin mark and a dot at the other hours.
function markers() {
  const hourMark = `style="stroke:var(--clock-markers)"`;
  const marks = [];
  for (let minute = 0; minute < 60; minute += 1) {
    const degrees = minute * 6;
    if (minute % 5 !== 0) {
      marks.push(spoke(degrees, R - 8, R - 3, `stroke-width="1" style="stroke:var(--text-tertiary)"`));
    } else if (minute % 15 === 0) {
      marks.push(spoke(degrees, R - 15, R - 5, `stroke-width="3" ${hourMark}`));
    } else {
      const [cx, cy] = point(degrees, R - 10);
      marks.push(spoke(degrees, R - 15, R - 5, `stroke-width="1" ${hourMark}`));
      marks.push(`<circle cx="${cx}" cy="${cy}" r="2" style="fill:var(--clock-markers)"/>`);
    }
  }
  return marks.join("");
}

// As on the TFT, the minute hand steps once a minute; only the hour hand creeps.
function hands(z) {
  const hand = `stroke-linecap="round" style="stroke:var(--clock-hands)"`;
  return [
    spoke(((z.hour % 12) + z.minute / 60) * 30, 0, R * 0.5, `stroke-width="6" ${hand}`),
    spoke(z.minute * 6, 0, R * 0.75, `stroke-width="4" ${hand}`),
    spoke(z.second * 6, 0, R * 0.85, `stroke-width="2" stroke="${SECOND_HAND}"`),
  ].join("");
}
