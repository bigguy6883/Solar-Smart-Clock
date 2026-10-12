import { test } from "node:test";
import assert from "node:assert/strict";

import { linePath, n, scale } from "../../solar_clock/web/js/svg.js";
import { HOSTILE } from "./fixtures.mjs";

test("n() writes short numbers and never passes text through", () => {
  assert.equal(n(12.34), "12.3");
  assert.equal(n(12), "12");
  assert.equal(n(-0.04), "0");
  assert.equal(n(HOSTILE), "NaN");
  assert.equal(n(null), "0");
});

test("scale() maps a data range onto a pixel range, either way up", () => {
  const y = scale(40, -90, 56, 176); // the Sun Path chart: 40° on top
  assert.equal(y(40), 56);
  assert.equal(y(-90), 176);
  assert.equal(n(y(0)), "92.9");
  assert.ok(y(73) < 56); // above the range lands above the box
});

test("linePath() joins points and is empty when there is no line", () => {
  assert.equal(linePath([[0, 1.26], [10, 2], [20.55, 3]]), "M0 1.3L10 2L20.6 3");
  assert.equal(linePath([[5, 5]]), "");
  assert.equal(linePath([]), "");
});
