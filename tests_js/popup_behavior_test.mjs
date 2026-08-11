// Runs the ACTUAL extension/popup.html + config.js + popup.js (read from
// disk, unmodified) inside jsdom, with chrome.* and fetch mocked, and
// exercises the real state-transition logic: initial tab-info load,
// successful LOW/HIGH analysis rendering, and the distinct failure
// states (offline, 503 model-unavailable) added in this project's
// Phase 7 work.
//
// popup.js is loaded as a classic (non-module) script, so its top-level
// `function`/`async function` declarations become properties of
// `window` -- this test calls those directly (window.showActiveTabInfo,
// window.analyzeCurrentPage) rather than simulating clicks + polling,
// which is both simpler and exercises the exact real functions.
//
// Exits 0 / "ALL PASSED" on success, 1 with details on failure.

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXT_DIR = path.join(__dirname, "..", "extension");

const POPUP_CSS = fs.readFileSync(path.join(EXT_DIR, "popup.css"), "utf8");
const POPUP_HTML = fs.readFileSync(path.join(EXT_DIR, "popup.html"), "utf8")
  // Strip the two <script src> tags -- we eval their real source
  // manually after installing chrome/fetch mocks, since runScripts
  // executes inline/external scripts synchronously during parsing,
  // before we'd get a chance to inject the mocks popup.js needs
  // immediately (showActiveTabInfo() runs at the bottom of the file).
  .replace(/<script src="config\.js"><\/script>\s*/, "")
  .replace(/<script src="popup\.js"><\/script>\s*/, "")
  // jsdom doesn't fetch external stylesheets by default (no `resources`
  // option set below), so <link rel="stylesheet" href="popup.css"> is a
  // no-op here -- inline the real popup.css so getComputedStyle() below
  // reflects the actual cascade (this is what caught the #analyzing /
  // .error-state specificity bug that classList-only assertions missed:
  // real Chrome testing found the loading spinner and the retry box
  // stayed visibly stuck on screen under the final result, because
  // `#analyzing { display: flex }` and `.error-state { display: flex }`
  // outrank/out-order `.hidden { display: none }` in the cascade even
  // once popup.js correctly adds the "hidden" class).
  .replace(/<link rel="stylesheet" href="popup\.css" \/>/, `<style>${POPUP_CSS}</style>`);
const CONFIG_SRC = fs.readFileSync(path.join(EXT_DIR, "config.js"), "utf8");
const POPUP_SRC = fs.readFileSync(path.join(EXT_DIR, "popup.js"), "utf8");

function makeChromeMock({ tabUrl, tabId = 1, extractedFeatures, executeScriptImpl }) {
  const calls = { executeScript: [] };
  return {
    calls,
    chrome: {
      tabs: {
        query: async () => (tabUrl ? [{ id: tabId, url: tabUrl }] : [{ id: tabId, url: "chrome://newtab" }]),
        goBack: async () => {
          throw new Error("no history in test");
        },
        update: async () => {},
      },
      scripting: {
        executeScript: async (opts) => {
          calls.executeScript.push(opts);
          if (executeScriptImpl) return executeScriptImpl(opts);
          if (opts.files && opts.files[0] === "page_extractor.js") {
            return [{ result: extractedFeatures }];
          }
          return [{ result: undefined }];
        },
      },
    },
  };
}

async function buildPopup({ chromeMock, fetchMock }) {
  const dom = new JSDOM(POPUP_HTML, { url: "chrome-extension://fake-id/popup.html", runScripts: "dangerously", pretendToBeVisual: true });
  dom.window.chrome = chromeMock;
  dom.window.fetch = fetchMock;
  // Evaluated together in one call, not two separate `eval()` calls --
  // jsdom's window.eval doesn't reliably persist a `const` from one
  // indirect-eval call into a later one, even though real browsers do
  // for two sequential <script> tags sharing global scope. Concatenating
  // is the faithful reproduction of that shared-scope behavior here.
  dom.window.eval(`${CONFIG_SRC}\n${POPUP_SRC}`);
  // popup.js's bottom-level `showActiveTabInfo()` call already ran
  // synchronously-up-to-its-first-await during eval; flush microtasks
  // so its async body (the chrome.tabs.query mock) completes.
  await flush();
  return dom;
}

function flush(times = 3) {
  let p = Promise.resolve();
  for (let i = 0; i < times; i++) p = p.then(() => new Promise((r) => setTimeout(r, 0)));
  return p;
}

function assertActuallyHidden(dom, el, label) {
  assert.ok(el.classList.contains("hidden"), `${label}: expected "hidden" class to be present`);
  const computedDisplay = dom.window.getComputedStyle(el).display;
  assert.equal(
    computedDisplay,
    "none",
    `${label}: has the "hidden" class but popup.css's cascade still renders it ` +
      `(computed display: "${computedDisplay}") -- a competing #id or later .class ` +
      `rule is winning over .hidden`
  );
}

// Regression test for a real bug found via live Chrome testing, not by
// this test suite: popup.js's setState() correctly toggled the "hidden"
// class on #analyzing/#error-state/#result, but #analyzing's ID selector
// and .error-state's later-declared class selector both out-specificity
// or out-order .hidden in popup.css, so the class was present in the DOM
// while the element stayed visually rendered. Every prior test here only
// asserted classList.contains("hidden"), which is exactly why this
// shipped undetected -- this test asserts the actual computed style.
async function test_hidden_class_actually_hides_every_state_section() {
  const { chrome } = makeChromeMock({
    tabUrl: "https://example.com/",
    extractedFeatures: { num_forms: 0, _meta_url: "https://example.com/", _meta_title: "Example" },
  });
  const fetchMock = async () => ({
    ok: true,
    status: 200,
    json: async () => ({ risk_score: 4, risk_band: "low", reasons: [], classifier_score: 0.01, judge_score: 0.0 }),
  });
  const dom = await buildPopup({ chromeMock: chrome, fetchMock });

  // Before any click: analyzing/error/result all start hidden.
  assertActuallyHidden(dom, dom.window.document.getElementById("analyzing"), "analyzing (initial)");
  assertActuallyHidden(dom, dom.window.document.getElementById("error-state"), "error-state (initial)");
  assertActuallyHidden(dom, dom.window.document.getElementById("result"), "result (initial)");

  await dom.window.analyzeCurrentPage();
  await flush();

  // After a successful analysis: analyzing and error-state must both
  // have actually disappeared, not just lost visibility to the human eye
  // by coincidence -- this is what "there is a loading always going on"
  // looked like in real Chrome.
  assertActuallyHidden(dom, dom.window.document.getElementById("analyzing"), "analyzing (after success)");
  assertActuallyHidden(dom, dom.window.document.getElementById("error-state"), "error-state (after success)");
  assert.notEqual(
    dom.window.getComputedStyle(dom.window.document.getElementById("result")).display,
    "none",
    "result should be visible (not display:none) once a result has rendered"
  );
}

async function test_initial_load_enables_analyze_on_a_normal_page() {
  const { chrome } = makeChromeMock({ tabUrl: "https://example.com/page" });
  const dom = await buildPopup({ chromeMock: chrome, fetchMock: async () => { throw new Error("not used"); } });
  const btn = dom.window.document.getElementById("analyze-btn");
  const info = dom.window.document.getElementById("page-info");
  assert.equal(btn.disabled, false);
  assert.equal(info.textContent, "https://example.com/page");
}

async function test_initial_load_disables_analyze_on_a_restricted_page() {
  const { chrome } = makeChromeMock({ tabUrl: "chrome://extensions" });
  const dom = await buildPopup({ chromeMock: chrome, fetchMock: async () => { throw new Error("not used"); } });
  const btn = dom.window.document.getElementById("analyze-btn");
  assert.equal(btn.disabled, true);
}

async function test_low_risk_result_renders_correctly() {
  const { chrome } = makeChromeMock({
    tabUrl: "https://example.com/",
    extractedFeatures: { num_forms: 0, _meta_url: "https://example.com/", _meta_title: "Example" },
  });
  const fetchMock = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      risk_score: 4,
      risk_band: "low",
      reasons: [],
      classifier_score: 0.01,
      judge_score: 0.0,
      model_version: "abc123def456",
    }),
  });
  const dom = await buildPopup({ chromeMock: chrome, fetchMock });

  await dom.window.analyzeCurrentPage();

  const resultEl = dom.window.document.getElementById("result");
  const errorEl = dom.window.document.getElementById("error-state");
  const analyzingEl = dom.window.document.getElementById("analyzing");
  const riskCard = dom.window.document.getElementById("risk-card");
  const highActions = dom.window.document.getElementById("high-risk-actions");

  assert.equal(resultEl.classList.contains("hidden"), false, "result section should be visible");
  assert.equal(errorEl.classList.contains("hidden"), true, "error section should stay hidden");
  assert.equal(
    analyzingEl.classList.contains("hidden"),
    true,
    "'Checking this page...' spinner must NOT remain visible once a result has rendered"
  );
  assert.ok(riskCard.className.includes("low"), `expected 'low' class, got: ${riskCard.className}`);
  assert.equal(dom.window.document.getElementById("risk-label").textContent, "LOW RISK");
  assert.equal(dom.window.document.getElementById("risk-score").textContent, "4 / 100");
  assert.equal(highActions.classList.contains("hidden"), true, "leave/continue actions should be hidden for LOW risk");
  assert.ok(
    dom.window.document.getElementById("analyzed-at").textContent.includes("abc123def456"),
    "model version should be shown in details"
  );

  // "View details" toggle: should be collapsed by default, expand on
  // click with the real classifier/judge/model-version text, and
  // collapse again on a second click.
  const detailsEl = dom.window.document.getElementById("details");
  const detailsToggle = dom.window.document.getElementById("details-toggle");
  assert.equal(detailsEl.classList.contains("hidden"), true, "details should be collapsed by default");

  detailsToggle.click();
  assert.equal(detailsEl.classList.contains("hidden"), false, "details should expand after clicking 'View details'");
  assert.equal(dom.window.document.getElementById("classifier-score").textContent, "classifier: 1.0%");
  assert.equal(dom.window.document.getElementById("judge-score").textContent, "judge: 0.0%");

  detailsToggle.click();
  assert.equal(detailsEl.classList.contains("hidden"), true, "details should collapse again on a second click");
}

async function test_high_risk_result_renders_and_triggers_overlay_injection() {
  const { chrome, calls } = makeChromeMock({
    tabUrl: "https://evil.example/login",
    extractedFeatures: { num_password_fields: 1, _meta_url: "https://evil.example/login", _meta_title: "Fake Login" },
  });
  const fetchMock = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      risk_score: 91,
      risk_band: "high",
      reasons: ["Suspicious domain", "Login form detected"],
      classifier_score: 0.99,
      judge_score: 0.85,
      model_version: "abc123def456",
    }),
  });
  const dom = await buildPopup({ chromeMock: chrome, fetchMock });

  await dom.window.analyzeCurrentPage();
  await flush();

  const riskCard = dom.window.document.getElementById("risk-card");
  assert.ok(riskCard.className.includes("high"));
  assert.equal(dom.window.document.getElementById("high-risk-actions").classList.contains("hidden"), false);
  const reasons = [...dom.window.document.querySelectorAll("#reasons li")].map((li) => li.textContent);
  assert.deepEqual(reasons, ["Suspicious domain", "Login form detected"]);

  const overlayInjectionCalls = calls.executeScript.filter((c) => c.files && c.files[0] === "page_overlay.js");
  assert.equal(overlayInjectionCalls.length, 1, "the overlay script should be injected exactly once for a HIGH verdict");
}

async function test_network_failure_shows_offline_error_state() {
  const { chrome } = makeChromeMock({
    tabUrl: "https://example.com/",
    extractedFeatures: { num_forms: 0, _meta_url: "https://example.com/", _meta_title: "Example" },
  });
  const fetchMock = async () => {
    throw new TypeError("Failed to fetch");
  };
  const dom = await buildPopup({ chromeMock: chrome, fetchMock });

  await dom.window.analyzeCurrentPage();

  const resultEl = dom.window.document.getElementById("result");
  const errorEl = dom.window.document.getElementById("error-state");
  assert.equal(resultEl.classList.contains("hidden"), true, "result should NOT show a stale/fake score on failure");
  assert.equal(errorEl.classList.contains("hidden"), false);
  const message = dom.window.document.getElementById("error-message").textContent;
  assert.match(message, /Couldn't reach the PhishShield backend/);
}

async function test_503_shows_model_unavailable_error_state_with_backend_detail() {
  const { chrome } = makeChromeMock({
    tabUrl: "https://example.com/",
    extractedFeatures: { num_forms: 0, _meta_url: "https://example.com/", _meta_title: "Example" },
  });
  const fetchMock = async () => ({
    ok: false,
    status: 503,
    json: async () => ({ detail: "model unavailable: artifacts/phishing_classifier.joblib not found." }),
  });
  const dom = await buildPopup({ chromeMock: chrome, fetchMock });

  await dom.window.analyzeCurrentPage();

  const errorEl = dom.window.document.getElementById("error-state");
  assert.equal(errorEl.classList.contains("hidden"), false);
  const message = dom.window.document.getElementById("error-message").textContent;
  assert.match(message, /model unavailable/);
}

async function test_retry_button_re_triggers_analysis() {
  const { chrome } = makeChromeMock({
    tabUrl: "https://example.com/",
    extractedFeatures: { num_forms: 0, _meta_url: "https://example.com/", _meta_title: "Example" },
  });
  let callCount = 0;
  const fetchMock = async () => {
    callCount += 1;
    if (callCount === 1) throw new TypeError("Failed to fetch");
    return {
      ok: true,
      status: 200,
      json: async () => ({ risk_score: 4, risk_band: "low", reasons: [], classifier_score: 0.01, judge_score: 0.0 }),
    };
  };
  const dom = await buildPopup({ chromeMock: chrome, fetchMock });

  await dom.window.analyzeCurrentPage();
  assert.equal(dom.window.document.getElementById("error-state").classList.contains("hidden"), false);

  dom.window.document.getElementById("retry-btn").click();
  await flush();

  assert.equal(callCount, 2, "retry should trigger a second fetch attempt");
  assert.equal(dom.window.document.getElementById("result").classList.contains("hidden"), false);
}

const tests = [
  test_hidden_class_actually_hides_every_state_section,
  test_initial_load_enables_analyze_on_a_normal_page,
  test_initial_load_disables_analyze_on_a_restricted_page,
  test_low_risk_result_renders_correctly,
  test_high_risk_result_renders_and_triggers_overlay_injection,
  test_network_failure_shows_offline_error_state,
  test_503_shows_model_unavailable_error_state_with_backend_detail,
  test_retry_button_re_triggers_analysis,
];

let failures = 0;
for (const test of tests) {
  try {
    await test();
    console.log(`PASS: ${test.name}`);
  } catch (err) {
    failures += 1;
    console.error(`FAIL: ${test.name}`);
    console.error(err);
  }
}

if (failures > 0) {
  console.error(`\n${failures}/${tests.length} FAILED`);
  process.exit(1);
} else {
  console.log(`\nALL PASSED (${tests.length}/${tests.length})`);
  process.exit(0);
}
