// Just enough of a browser for app.js: the five page elements, events, the
// root style, location/history and fetch. setInterval is recorded, not run.

function eventTarget(extra = {}) {
  const handlers = {};
  return Object.assign(
    {
      addEventListener(type, fn) {
        (handlers[type] ??= []).push(fn);
      },
      dispatch(type, event = {}) {
        for (const fn of handlers[type] ?? []) fn(event);
      },
    },
    extra,
  );
}

const GLOBALS = ["document", "window", "location", "history", "fetch", "setInterval"];

/**
 * Install a fake page. `responses` are served to fetch("/api/now") in order,
 * and `charts` to fetch("/api/charts"): an object is a 200 JSON body, an Error
 * is a network failure, a number is that HTTP status, null never answers.
 */
export function installDom({ hash = "", responses = [], charts = [] } = {}) {
  const saved = Object.fromEntries(GLOBALS.map((name) => [name, globalThis[name]]));
  const elements = {};
  for (const id of ["banner", "view", "dots", "prev", "next"]) {
    elements[id] = eventTarget({
      innerHTML: "",
      textContent: "",
      hidden: false,
      attributes: {},
      setAttribute(name, value) {
        this.attributes[name] = value;
      },
    });
  }
  const rootStyle = {
    props: {},
    colorScheme: "",
    setProperty(name, value) {
      this.props[name] = value;
    },
  };
  const location = { hash };
  const fetchCalls = [];
  Object.assign(globalThis, {
    document: eventTarget({
      visibilityState: "visible",
      documentElement: { style: rootStyle },
      getElementById: (id) => elements[id],
    }),
    window: eventTarget(),
    location,
    history: {
      replaceState(_state, _title, url) {
        location.hash = url;
      },
    },
    fetch(url, options) {
      fetchCalls.push({ url, options });
      const next = (url === "/api/charts" ? charts : responses).shift();
      if (next === null || next === undefined) return new Promise(() => {});
      if (next instanceof Error) return Promise.reject(next);
      if (typeof next === "number") return Promise.resolve({ ok: false, status: next });
      return Promise.resolve({ ok: true, status: 200, json: async () => next });
    },
    setInterval: () => 0,
  });
  return {
    elements,
    rootStyle,
    location,
    fetchCalls,
    responses,
    charts,
    restore() {
      Object.assign(globalThis, saved);
    },
  };
}

/** Let pending promises (the fetch and its .json()) settle. */
export async function settle() {
  for (let i = 0; i < 5; i += 1) await new Promise((resolve) => setImmediate(resolve));
}

let loads = 0;

/** Run app.js against the installed page; each call gets a fresh copy. */
export async function loadApp() {
  loads += 1;
  await import(`../../solar_clock/web/js/app.js?load=${loads}`);
  await settle();
}
