// Weather view: mirrors solar_clock/views/weather.py.

import { escapeHtml, fixed, weekdayShort } from "../format.js";
import { namedColors } from "../theme.js";

export const name = "weather";
export const title = "Weather";

const NEAR_DAYS = ["Today", "Tmrw"];

export function render(data) {
  const colors = namedColors(data);
  const header = `<header class="view-header" style="background:${colors.LIGHT_BLUE}"><h2>Weather</h2></header>`;
  const footer = `<p class="footer"><span>${escapeHtml(data.location.name)}</span></p>`;
  const current = data.weather?.current;
  if (!current) {
    return `${header}<div class="view-body"><p class="message">Weather data unavailable</p>${footer}</div>`;
  }
  const unit = data.units === "metric" ? "°C" : "°F";
  return `${header}
<div class="view-body">
  <div class="row">
    <section class="panel">
      <span class="temp-big">${fixed(current.temperature)}${unit}</span>
      <span class="secondary small">Feels ${fixed(current.feels_like)}°</span>
      <span class="secondary small">Humidity ${escapeHtml(current.humidity)}%</span>
      <span class="secondary small">Wind ${fixed(current.wind_speed)} ${escapeHtml(current.wind_direction)}</span>
      <span class="sun description">${escapeHtml(current.description)}</span>
    </section>
    <section class="panel">${forecastTable(data.weather.forecast)}</section>
  </div>
  ${footer}
</div>`;
}

function forecastTable(days) {
  const rows = days
    .slice(0, 3)
    .map((day, i) => {
      const label = i < NEAR_DAYS.length ? NEAR_DAYS[i] : weekdayShort(day.date);
      const rain = day.rain_chance < 30 ? "secondary" : "cool";
      return `<tr><td>${label}</td><td class="num warm">${fixed(day.high_temp)}°</td><td class="num cool">${fixed(day.low_temp)}°</td><td class="${rain}">${escapeHtml(day.rain_chance)}%</td></tr>`;
    })
    .join("");
  return `<table class="forecast">
      <thead><tr><th>Day</th><th>Hi</th><th>Lo</th><th>Rain</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
