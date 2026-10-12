// Navigation rules for the page. They never touch the physical clock.

export const SWIPE_MIN_PX = 50;

/** Index after moving `delta` views, wrapping at both ends. */
export function wrapIndex(index, delta, count) {
  return (((index + delta) % count) + count) % count;
}

/** The view the page opens on when the link names none. */
export const DEFAULT_VIEW = "sunpath";

/** View index named by a URL hash such as "#moon"; the default view when unknown. */
export function indexFromHash(hash, names) {
  const index = names.indexOf(hash.replace(/^#/, "").toLowerCase());
  return index === -1 ? Math.max(0, names.indexOf(DEFAULT_VIEW)) : index;
}

/**
 * +1 (next view) for a swipe from right to left, -1 (previous) for a swipe
 * from left to right, else 0. This is the usual phone direction; the TFT goes
 * the other way (touch_handler.py: dx > 0 is next).
 */
export function swipeDelta(dx, dy) {
  if (Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) <= Math.abs(dy)) return 0;
  return dx < 0 ? 1 : -1;
}
