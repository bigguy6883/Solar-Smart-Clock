import { afterEach, test } from "node:test";
import assert from "node:assert/strict";

import { VIEWS } from "../../solar_clock/web/js/views/index.js";
import { installDom, loadApp, settle } from "./dom-stub.mjs";
import { sampleNow } from "./fixtures.mjs";

// Written against the view list, so it holds as views are added.
const names = VIEWS.map((v) => v.name);
const nameAt = (i) => names[((i % names.length) + names.length) % names.length];

let page;
afterEach(() => page.restore());

function dayData() {
  const data = sampleNow();
  data.theme.active = "day";
  return data;
}

test("before the first answer the page says it is connecting", async () => {
  page = installDom({ responses: [null] });
  await loadApp();
  assert.equal(page.elements.banner.hidden, false);
  assert.equal(page.elements.banner.textContent, "Connecting to clock…");
  assert.equal(page.elements.view.innerHTML, "");
});

test("the first answer draws the Clock view in the clock's theme", async () => {
  page = installDom({ responses: [sampleNow()] });
  await loadApp();
  assert.equal(page.fetchCalls[0].url, "/api/now");
  assert.equal(page.fetchCalls[0].options.cache, "no-store");
  assert.equal(page.elements.banner.hidden, true);
  assert.match(page.elements.view.innerHTML, /Sunrise/);
  assert.equal(page.rootStyle.props["--background"], "#000000");
  assert.equal(page.rootStyle.colorScheme, "dark");
});

test("losing the clock keeps the last data and says so, then recovers", async () => {
  page = installDom({ responses: [sampleNow(), new Error("offline")] });
  await loadApp();
  document.dispatch("visibilitychange"); // waking the page polls at once
  await settle();
  assert.equal(page.fetchCalls.length, 2);
  assert.equal(page.elements.banner.hidden, false);
  assert.match(page.elements.banner.textContent, /^Can't reach clock · last update \d{1,2}:\d\d [AP]M$/);
  assert.match(page.elements.view.innerHTML, /Sunrise/);

  page.responses.push(sampleNow());
  document.dispatch("visibilitychange");
  await settle();
  assert.equal(page.elements.banner.hidden, true);
});

test("a theme change on the clock reaches an open page", async () => {
  page = installDom({ responses: [sampleNow(), dayData()] });
  await loadApp();
  document.dispatch("visibilitychange");
  await settle();
  assert.equal(page.rootStyle.props["--background"], "#f5f3eb");
  assert.equal(page.rootStyle.colorScheme, "light");
});

test("a link to a view opens it; buttons and arrow keys move and wrap", async () => {
  const last = names.length - 1;
  page = installDom({ hash: `#${nameAt(last)}`, responses: [sampleNow()] });
  await loadApp();
  assert.equal(page.elements.dots.attributes["aria-label"], `${VIEWS[last].title}, view ${last + 1} of ${names.length}`);

  page.elements.next.dispatch("click");
  assert.equal(page.location.hash, `#${nameAt(0)}`);
  assert.match(page.elements.view.innerHTML, /Sunrise/);

  document.dispatch("keydown", { key: "ArrowLeft" });
  assert.equal(page.location.hash, `#${nameAt(last)}`);
  page.elements.prev.dispatch("click");
  assert.equal(page.location.hash, `#${nameAt(last - 1)}`);
});

test("an unknown link opens Clock", async () => {
  page = installDom({ hash: "#nowhere", responses: [sampleNow()] });
  await loadApp();
  assert.match(page.elements.view.innerHTML, /Sunrise/);
});

test("a swipe right moves to the next view, as on the TFT; a vertical drag does not", async () => {
  page = installDom({ responses: [sampleNow()] });
  await loadApp();
  const swipe = (from, to) => {
    page.elements.view.dispatch("touchstart", { changedTouches: [from] });
    page.elements.view.dispatch("touchend", { changedTouches: [to] });
  };
  swipe({ clientX: 200, clientY: 100 }, { clientX: 190, clientY: 400 });
  assert.equal(page.location.hash, "");
  swipe({ clientX: 120, clientY: 200 }, { clientX: 300, clientY: 210 });
  assert.equal(page.location.hash, `#${nameAt(1)}`);
});

test("a view that throws shows a message instead of a blank page", async () => {
  const broken = sampleNow();
  broken.location = null; // every view reads location
  page = installDom({ responses: [broken] });
  await loadApp();
  assert.equal(page.elements.view.innerHTML, `<p class="message">Couldn't draw this view</p>`);
  page.elements.next.dispatch("click");
  assert.equal(page.location.hash, `#${nameAt(1)}`);
});
