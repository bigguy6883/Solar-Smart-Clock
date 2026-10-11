// Colour rules copied from the TFT drawing code so the page matches it.

import { zoned } from "./format.js";

/** Fixed named colours from views/colors.py, e.g. colors.LIGHT_BLUE. */
export function namedColors(data) {
  return data.theme?.colors ?? {};
}

/** CSS custom properties for a palette: background_panel -> --background-panel. */
export function cssVariables(palette) {
  return Object.entries(palette).map(([key, value]) => [`--${key.replaceAll("_", "-")}`, value]);
}

/** Header colour for the time of day (BaseView.get_time_header_color). */
export function timeOfDayHeader(now, sun, colors, timeZone) {
  const times = sun?.times;
  if (times) {
    if (now < new Date(times.dawn)) return colors.DARK_BLUE;
    if (now < new Date(times.sunrise)) return colors.ORANGE;
    if (now < new Date(times.sunset)) return colors.LIGHT_BLUE;
    if (now < new Date(times.dusk)) return colors.ORANGE;
    return colors.PURPLE;
  }
  const { hour } = zoned(now, timeZone);
  if (hour < 6) return colors.DARK_BLUE;
  if (hour < 8) return colors.ORANGE;
  if (hour < 17) return colors.LIGHT_BLUE;
  if (hour < 20) return colors.ORANGE;
  return colors.PURPLE;
}

/** Darkened AQI colour behind the white title (AirQualityView._get_aqi_header_color). */
export function aqiHeaderColor(aqi, colors) {
  if (aqi <= 50) return "#00822d";
  if (aqi <= 100) return "#aa8200";
  if (aqi <= 150) return "#be5500";
  if (aqi <= 200) return "#b91e1e";
  if (aqi <= 300) return colors.AQI_VERY_UNHEALTHY;
  return colors.AQI_HAZARDOUS;
}

/** Colour of the AQI number and category (AirQualityView._get_aqi_text_color). */
export function aqiTextColor(aqi, themeName, colors) {
  if (themeName === "day") return aqiHeaderColor(aqi, colors);
  if (aqi <= 50) return colors.AQI_GOOD;
  if (aqi <= 100) return "#c8b400"; // darker yellow, readable on black
  if (aqi <= 150) return colors.AQI_UNHEALTHY_SENSITIVE;
  if (aqi <= 200) return colors.AQI_UNHEALTHY;
  if (aqi <= 300) return colors.AQI_VERY_UNHEALTHY;
  return colors.AQI_HAZARDOUS;
}

/** Pollutant bar colour by how full the bar is (AirQualityView._render_pollutants). */
export function pollutantBarColor(fraction, colors) {
  if (fraction < 0.5) return colors.AQI_GOOD;
  if (fraction < 0.75) return colors.AQI_MODERATE;
  return colors.AQI_UNHEALTHY;
}
