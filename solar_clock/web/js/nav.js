// Navigation rules for the page. They never touch the physical clock.

export const SWIPE_MIN_PX = 50;

/** Index after moving `delta` views, wrapping at both ends. */
export function wrapIndex(index, delta, count) {
  return (((index + delta) % count) + count) % count;
}

/** View index named by a URL hash such as "#moon"; 0 (Clock) when unknown. */
export function indexFromHash(hash, names) {
  const index = names.indexOf(hash.replace(/^#/, "").toLowerCase());
  return index === -1 ? 0 : index;
}

/**
 * +1 (next view) for a swipe right, -1 (previous) for a swipe left, else 0.
 * Same direction as the TFT (touch_handler.py: dx > 0 is next).
 */
export function swipeDelta(dx, dy) {
  if (Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) <= Math.abs(dy)) return 0;
  return dx > 0 ? 1 : -1;
}
