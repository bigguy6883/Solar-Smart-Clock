// Page shell: polls /api/now, fetches /api/charts once per day, redraws the
// current view every second, and handles navigation. It only reads from the
// clock; it never changes it.

import { time12 } from "./format.js";
import { indexFromHash, swipeDelta, wrapIndex } from "./nav.js";
import { cssVariables } from "./theme.js";
import { VIEWS } from "./views/index.js";

const POLL_MS = 60_000;
const TICK_MS = 1_000;

const els = {
  banner: document.getElementById("banner"),
  view: document.getElementById("view"),
  dots: document.getElementById("dots"),
  prev: document.getElementById("prev"),
  next: document.getElementById("next"),
};

const state = {
  data: null,
  charts: null,
  lastOk: null,
  failing: false,
  theme: null,
  index: indexFromHash(location.hash, VIEWS.map((v) => v.name)),
};

function applyTheme(theme) {
  if (!theme || theme.active === state.theme) return;
  for (const [name, value] of cssVariables(theme.palettes[theme.active])) {
    document.documentElement.style.setProperty(name, value);
  }
  document.documentElement.style.colorScheme = theme.active === "day" ? "light" : "dark";
  state.theme = theme.active;
}

function renderBanner() {
  if (state.data === null) {
    els.banner.textContent = "Connecting to clock…";
    els.banner.hidden = false;
  } else if (state.failing) {
    const last = time12(state.lastOk, state.data.location.timezone);
    els.banner.textContent = `Can't reach clock · last update ${last}`;
    els.banner.hidden = false;
  } else {
    els.banner.hidden = true;
  }
}

function renderDots() {
  els.dots.innerHTML = VIEWS.map(
    (v, i) => `<span class="dot${i === state.index ? " active" : ""}"></span>`,
  ).join("");
  els.dots.setAttribute("aria-label", `${VIEWS[state.index].title}, view ${state.index + 1} of ${VIEWS.length}`);
}

function render() {
  renderBanner();
  renderDots();
  if (state.data === null) return;
  const view = VIEWS[state.index];
  try {
    els.view.innerHTML = view.render({ ...state.data, charts: state.charts }, new Date());
  } catch (err) {
    console.error(`The ${view.name} view failed to draw`, err);
    els.view.innerHTML = `<p class="message">Couldn't draw this view</p>`;
  }
}

async function poll() {
  try {
    const response = await fetch("/api/now", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    state.lastOk = new Date();
    state.failing = false;
    applyTheme(state.data.theme);
  } catch (err) {
    console.warn("Could not reach the clock", err);
    state.failing = true;
  }
  render();
  if (!state.failing && chartsAreStale()) await loadCharts();
}

// The clock works its charts out once per day, so they are fetched when the
// page has none or the clock's date has moved on. The date comes from the
// clock's answer, not this device, so a wrong phone clock can't cause refetching.
function chartsAreStale() {
  return state.charts === null || state.charts.date !== state.data.generated_at.slice(0, 10);
}

// A failure leaves the old charts (or none) in place; the next poll tries again.
async function loadCharts() {
  try {
    const response = await fetch("/api/charts", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.charts = await response.json();
    render();
  } catch (err) {
    console.warn("Could not load the charts", err);
  }
}

function go(delta) {
  state.index = wrapIndex(state.index, delta, VIEWS.length);
  history.replaceState(null, "", `#${VIEWS[state.index].name}`);
  render();
}

els.prev.addEventListener("click", () => go(-1));
els.next.addEventListener("click", () => go(1));
document.addEventListener("keydown", (e) => {
  if (e.key === "ArrowLeft") go(-1);
  if (e.key === "ArrowRight") go(1);
});
window.addEventListener("hashchange", () => {
  state.index = indexFromHash(location.hash, VIEWS.map((v) => v.name));
  render();
});

let touchStart = null;
els.view.addEventListener("touchstart", (e) => {
  const t = e.changedTouches[0];
  touchStart = { x: t.clientX, y: t.clientY };
}, { passive: true });
els.view.addEventListener("touchend", (e) => {
  if (touchStart === null) return;
  const t = e.changedTouches[0];
  const delta = swipeDelta(t.clientX - touchStart.x, t.clientY - touchStart.y);
  touchStart = null;
  if (delta !== 0) go(delta);
}, { passive: true });

// A phone reopening the page from the home screen gets fresh data at once.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") poll();
});

render();
poll();
setInterval(poll, POLL_MS);
setInterval(render, TICK_MS);
