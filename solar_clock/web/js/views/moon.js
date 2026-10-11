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
    <section class="panel"><span class="label">New Moon</span><span class="value">${shortDate(p.next_new)} <span class="secondary small">${p.days_to_new}d</span></span></section>
    <section class="panel"><span class="label">Full Moon</span><span class="value moon">${shortDate(p.next_full)} <span class="secondary small">${p.days_to_full}d</span></span></section>
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

/** Shadow over the disc, drawn the way MoonView._render_moon_graphic draws it. */
export function moonShadow(phase) {
  if (phase < 0.03 || phase > 0.97) return `<circle cx="${C}" cy="${C}" r="${R}" fill="${SHADOW}"/>`;
  if (phase >= 0.47 && phase <= 0.53) return "";
  // Waxing: shadow on the left; waning: on the right (northern hemisphere).
  const width = Math.trunc(Math.abs(phase - 0.5) * 2 * R * 2);
  const cx = phase < 0.5 ? C - R + width / 2 : C + R - width / 2;
  return `<ellipse cx="${cx}" cy="${C}" rx="${width / 2}" ry="${R}" fill="${SHADOW}"/>`;
}
