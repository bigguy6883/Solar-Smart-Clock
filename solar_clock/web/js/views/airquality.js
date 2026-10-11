// Air Quality view: mirrors solar_clock/views/airquality.py.

import { escapeHtml, fixed, time12 } from "../format.js";
import { aqiHeaderColor, aqiTextColor, namedColors, pollutantBarColor } from "../theme.js";

export const name = "airquality";
export const title = "Air Quality";

// [label, field, value that fills the bar]
const POLLUTANTS = [
  ["PM2.5", "pm25", 50],
  ["PM10", "pm10", 100],
  ["O3", "o3", 100],
  ["NO2", "no2", 50],
  ["CO", "co", 5000],
];
// The TFT's bars are 120 px wide and it skips fills of 3 px or less.
const TFT_BAR_PX = 120;

export function render(data) {
  const aq = data.air_quality;
  // As on the TFT: no header at all when there is no data.
  if (!aq) return `<div class="view-body"><p class="message">No data available</p></div>`;
  const colors = namedColors(data);
  const text = aqiTextColor(aq.aqi, data.theme?.active, colors);
  const rows = POLLUTANTS.map(([label, field, max]) => pollutant(label, aq[field], max, colors));
  return `<header class="view-header" style="background:${aqiHeaderColor(aq.aqi, colors)}"><h2>Air Quality</h2></header>
<div class="view-body">
  <div class="row">
    <section class="panel dark">
      <span class="label">US EPA AQI</span>
      <span class="aqi-value" style="color:${text}">${aq.aqi}</span>
      <span class="aqi-category" style="color:${text}">${escapeHtml(aq.category)}</span>
    </section>
    <section class="panel dark">
      <h3 class="panel-title">Pollutants</h3>
      ${rows.join("")}
    </section>
  </div>
  <p class="footer"><span>${escapeHtml(data.location.name)}</span><span>Updated ${time12(aq.updated_at, data.location.timezone)}</span></p>
</div>`;
}

function pollutant(label, value, max, colors) {
  const fraction = Math.min(value / max, 1);
  const fill =
    Math.trunc(TFT_BAR_PX * fraction) > 3
      ? `<span class="pollutant-fill" style="width:${(fraction * 100).toFixed(1)}%;background:${pollutantBarColor(fraction, colors)}"></span>`
      : "";
  return `<div class="pollutant"><span class="pollutant-name">${label}</span><span class="pollutant-bar">${fill}</span><span class="pollutant-value">${fixed(value, 1)}</span></div>`;
}
