import { test } from "node:test";
import assert from "node:assert/strict";

import { indexFromHash, swipeDelta, wrapIndex } from "../../solar_clock/web/js/nav.js";

test("navigation wraps at both ends", () => {
  assert.equal(wrapIndex(4, 1, 5), 0);
  assert.equal(wrapIndex(0, -1, 5), 4);
  assert.equal(wrapIndex(2, 1, 5), 3);
});

test("the URL hash picks the view; without one the page opens on Sun Path", () => {
  const names = ["clock", "weather", "sunpath", "moon"];
  assert.equal(indexFromHash("#moon", names), 3);
  assert.equal(indexFromHash("#MOON", names), 3);
  assert.equal(indexFromHash("#clock", names), 0);
  assert.equal(indexFromHash("", names), 2);
  assert.equal(indexFromHash("#nope", names), 2);
  assert.equal(indexFromHash("", ["clock", "weather"]), 0); // no Sun Path: the first view
});

test("a clear horizontal swipe moves one view; anything else is ignored", () => {
  assert.equal(swipeDelta(-80, 10), 1); // right to left = next, as on any phone
  assert.equal(swipeDelta(80, 10), -1);
  assert.equal(swipeDelta(30, 0), 0);
  assert.equal(swipeDelta(80, 120), 0);
});
