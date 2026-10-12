// Text formatting that matches the TFT's strftime patterns. Times are shown in
// the clock's configured timezone, not the viewer's.

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const WEEKDAYS_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const formatters = new Map();

function formatterFor(timeZone) {
  let formatter = formatters.get(timeZone);
  if (formatter === undefined) {
    formatter = new Intl.DateTimeFormat("en-US", {
      timeZone,
      hourCycle: "h23",
      weekday: "long",
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
    });
    formatters.set(timeZone, formatter);
  }
  return formatter;
}

function toDate(value) {
  return value instanceof Date ? value : new Date(value);
}

const pad2 = (n) => String(n).padStart(2, "0");
const hour12 = (hour) => hour % 12 || 12;

/** Wall-clock fields of an instant (Date or ISO string) in `timeZone`. */
export function zoned(value, timeZone) {
  const parts = {};
  for (const part of formatterFor(timeZone).formatToParts(toDate(value))) {
    parts[part.type] = part.value;
  }
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour) % 24,
    minute: Number(parts.minute),
    second: Number(parts.second),
    weekday: parts.weekday,
  };
}

/** "%-I:%M %p", e.g. "6:42 AM". */
export function time12(value, timeZone) {
  const z = zoned(value, timeZone);
  return `${hour12(z.hour)}:${pad2(z.minute)} ${z.hour < 12 ? "AM" : "PM"}`;
}

/** "%-I:%M", e.g. "6:42" (the start of a golden-hour range). */
export function time12Bare(value, timeZone) {
  const z = zoned(value, timeZone);
  return `${hour12(z.hour)}:${pad2(z.minute)}`;
}

/** Clock header: "%-I:%M:%S" and "%p". */
export function clockParts(now, timeZone) {
  const z = zoned(now, timeZone);
  return {
    time: `${hour12(z.hour)}:${pad2(z.minute)}:${pad2(z.second)}`,
    ampm: z.hour < 12 ? "AM" : "PM",
  };
}

/** "%A, %B %d, %Y", e.g. "Thursday, October 08, 2026". */
export function longDate(now, timeZone) {
  const z = zoned(now, timeZone);
  return `${z.weekday}, ${MONTHS[z.month - 1]} ${pad2(z.day)}, ${z.year}`;
}

/** "%a %b %d", e.g. "Thu Oct 08" (Sun Path view). */
export function shortWeekdayDate(now, timeZone) {
  const z = zoned(now, timeZone);
  return `${z.weekday.slice(0, 3)} ${MONTHS[z.month - 1].slice(0, 3)} ${pad2(z.day)}`;
}

/** "%A, %B %d", e.g. "Thursday, October 08" (Analog Clock view). */
export function weekdayDate(now, timeZone) {
  const z = zoned(now, timeZone);
  return `${z.weekday}, ${MONTHS[z.month - 1]} ${pad2(z.day)}`;
}

/** The "YYYY-MM-DD" date of an instant in `timeZone`. */
export function isoDate(value, timeZone) {
  const z = zoned(value, timeZone);
  return `${z.year}-${pad2(z.month)}-${pad2(z.day)}`;
}

function utcDay(isoDay) {
  const [year, month, day] = isoDay.split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

/** Whole days from one "YYYY-MM-DD" date to another; negative when `to` is earlier. */
export function daysBetween(from, to) {
  return Math.round((utcDay(to) - utcDay(from)) / 86_400_000);
}

/** The "YYYY-MM-DD" date `days` after (or, when negative, before) another. */
export function addDays(isoDay, days) {
  return new Date(utcDay(isoDay) + days * 86_400_000).toISOString().slice(0, 10);
}

/** "%b %d" for a "YYYY-MM-DD" date, e.g. "Oct 10". */
export function shortDate(isoDate) {
  const [, month, day] = isoDate.split("-").map(Number);
  return `${MONTHS[month - 1].slice(0, 3)} ${pad2(day)}`;
}

/** "%a" for a "YYYY-MM-DD" date, e.g. "Sat". */
export function weekdayShort(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return WEEKDAYS_SHORT[new Date(Date.UTC(year, month - 1, day)).getUTCDay()];
}

/** Whole hours and minutes, truncated like Python's int(). */
export function hoursMinutes(hours) {
  const h = Math.trunc(hours);
  return { h, m: Math.trunc((hours - h) * 60) };
}

/** Clock view day length, e.g. "11h 05m". */
export function dayLengthPadded(hours) {
  const { h, m } = hoursMinutes(hours);
  return `${h}h ${pad2(m)}m`;
}

/** Solar view day length, e.g. "11h 5m". */
export function dayLengthText(hours) {
  const { h, m } = hoursMinutes(hours);
  return `${h}h ${m}m`;
}

/** Hours and minutes from `now` until `target`; zero once it has passed. */
export function countdownHM(target, now) {
  const seconds = Math.max(0, (toDate(target) - toDate(now)) / 1000);
  return { h: Math.floor(seconds / 3600), m: Math.floor((seconds % 3600) / 60) };
}

/** Fraction (0-1) of the local day that has passed at `now`. */
export function dayFraction(now, timeZone) {
  const z = zoned(now, timeZone);
  return (z.hour * 3600 + z.minute * 60 + z.second) / 86400;
}

/** 8-point compass name for an azimuth in degrees (as ClockView). */
export function compass8(azimuth) {
  if (azimuth >= 337.5 || azimuth < 22.5) return "N";
  if (azimuth < 67.5) return "NE";
  if (azimuth < 112.5) return "E";
  if (azimuth < 157.5) return "SE";
  if (azimuth < 202.5) return "S";
  if (azimuth < 247.5) return "SW";
  if (azimuth < 292.5) return "W";
  return "NW";
}

/**
 * Python's format(value, ".Nf"). toFixed rounds exact halves away from zero
 * (64.5 -> "65") where Python rounds them to even ("64"), so ties are handled
 * here. A value is an exact tie at N digits when value * 2^(N+1) is an odd
 * integer; scaling by a power of two is exact.
 */
export function fixed(value, digits = 0) {
  const doubled = value * 2 ** (digits + 1);
  let text;
  if (Number.isInteger(doubled) && Math.abs(doubled % 2) === 1) {
    const scale = 10 ** digits;
    const lower = Math.floor(value * scale); // exact: value * scale is a half-integer
    const even = lower % 2 === 0 ? lower : lower + 1;
    text = (even / scale).toFixed(digits);
  } else {
    text = value.toFixed(digits);
  }
  // Python keeps the sign when a negative value rounds to zero ("-0").
  if (value < 0 && !text.startsWith("-")) text = `-${text}`;
  return text;
}

/** Escape text for insertion into HTML. */
export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ESCAPES[ch]);
}
