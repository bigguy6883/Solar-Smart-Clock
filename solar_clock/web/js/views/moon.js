// Moon Phase view: mirrors solar_clock/views/moon.py.

import { escapeHtml, fixed, shortDate, time12 } from "../format.js";
import { namedColors } from "../theme.js";

export const name = "moon";
export const title = "Moon Phase";

const R = 50; // disc radius, as on the TFT
const C = 55; // disc centre in a 110 x 110 viewBox
const SHADOW = "#1e1e1e"; // (30, 30, 30), the TFT's shadow colour

export function render(data) {
  const colors = namedColors(data);
  const header = `<header class="view-header" style="background:${colors.PURPLE}"><h2>Moon Phase</h2></header>`;
  const moon = data.moon;
  if (!moon) return `${header}<div class="view-body"><p class="message">Lunar data unavailable</p></div>`;
  const tz = data.location.timezone;
  const p = moon.phase;
  return `${header}
<div class="view-body">
  <div class="moon-top">
    ${moonDisc(p.phase, colors)}
    <div><span class="moon-illum">${fixed(p.illumination)}%</span><span class="moon block">${escapeHtml(p.phase_name)}</span></div>
  </div>
  <div class="row">
    ${timeBox("Moonrise", moon.times?.moonrise, tz)}
    ${timeBox("Moonset", moon.times?.moonset, tz)}
    <section class="panel boxed"><span class="label">Lunar Cycle</span>
      <span class="cycle"><span class="cycle-fill" style="width:${(p.phase * 100).toFixed(1)}%;background:${colors.PURPLE}"></span><span class="cycle-full"></span></span>
    </section>
  </div>
  <div class="row">
    <section class="panel"><span class="label">New Moon</span><span class="value">${shortDate(p.next_new)} <span class="secondary small">${escapeHtml(p.days_to_new)}d</span></span></section>
    <section class="panel"><span class="label">Full Moon</span><span class="value moon">${shortDate(p.next_full)} <span class="secondary small">${escapeHtml(p.days_to_full)}d</span></span></section>
  </div>
</div>`;
}

function timeBox(label, at, tz) {
  const value = at ? `<span class="value">${time12(at, tz)}</span>` : "";
  return `<section class="panel boxed"><span class="label">${label}</span>${value}</section>`;
}

function moonDisc(phase, colors) {
  return `<svg class="moon-disc" viewBox="0 0 110 110" role="img" aria-label="Moon phase">
      <circle cx="${C}" cy="${C}" r="${R}" fill="${colors.MOON_YELLOW}"/>${moonShadow(phase)}
      <circle cx="${C}" cy="${C}" r="${R}" fill="none" style="stroke:var(--text-tertiary)" stroke-width="1"/>
    </svg>`;
}

/**
 * Shadow over the disc: the dark half of the moon's edge, closed by the
 * terminator. MoonView's rules decide when the moon counts as new or full; the
 * partial shape is drawn true to the phase rather than as MoonView's ellipse,
 * which strays outside the disc.
 */
export function moonShadow(phase) {
  if (phase < 0.03 || phase > 0.97) return `<circle cx="${C}" cy="${C}" r="${R}" fill="${SHADOW}"/>`;
  if (phase >= 0.47 && phase <= 0.53) return "";
  // Waxing: shadow on the left; waning: on the right (northern hemisphere).
  const edge = phase < 0.5 ? 0 : 1; // arc direction, top to bottom along the dark edge
  const lean = Math.cos(phase * 2 * Math.PI); // > 0: a crescent is lit, < 0: gibbous
  const rx = Number((R * Math.abs(lean)).toFixed(2));
  const back = lean > 0 ? edge : 1 - edge; // the terminator bulges into the lit side for a crescent
  const top = `${C} ${C - R}`;
  const bottom = `${C} ${C + R}`;
  return `<path d="M${top}A${R} ${R} 0 0 ${edge} ${bottom}A${rx} ${R} 0 0 ${back} ${top}Z" fill="${SHADOW}"/>`;
}
