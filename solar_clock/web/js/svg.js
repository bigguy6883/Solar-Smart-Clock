// Small helpers for the chart views' inline SVG.

/** A number as SVG attribute text: one decimal at most, e.g. 12.34 -> "12.3". */
export function n(value) {
  return String(Math.round(Number(value) * 10) / 10);
}

/** A function mapping the range d0..d1 onto r0..r1 in a straight line. */
export function scale(d0, d1, r0, r1) {
  return (value) => r0 + ((value - d0) / (d1 - d0)) * (r1 - r0);
}

/** Path data for a line through [[x, y], ...]; "" when there is nothing to join. */
export function linePath(points) {
  if (points.length < 2) return "";
  return points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${n(x)} ${n(y)}`).join("");
}
