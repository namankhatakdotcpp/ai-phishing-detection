// Runs the ACTUAL extension/page_overlay.js source (unmodified, read
// from disk) inside jsdom and exercises its real interactive logic:
// initial focus, the two-item Tab focus trap, and Escape-to-dismiss.
//
// The shipped file uses a CLOSED shadow root by design (so a malicious
// page script can't reach into the warning and read/tamper with it --
// see page_overlay.js's own header comment). That's real security
// value we don't want to weaken, but it also means code outside the
// IIFE (i.e. this test) has no way to query into the shadow tree from a
// black-box position, the same real constraint a malicious page script
// would face. So: patch attachShadow to force "open" *before* running
// the real source, exercise its logic with full visibility, then
// restore the original. This tests the exact real file's control flow
// end to end, not a hand-copied duplicate -- only the shadow-root
// visibility is different, purely for test introspection.
//
// Exits 0 and prints "ALL PASSED" on success, exits 1 with details on
// any failure (checked via node:assert, which throws on mismatch).

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OVERLAY_PATH = path.join(__dirname, "..", "extension", "page_overlay.js");

function freshDom() {
  const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
    url: "https://example.com/",
    pretendToBeVisual: true, // needed for .focus() to actually move activeElement in jsdom
  });
  const OriginalAttachShadow = dom.window.Element.prototype.attachShadow;
  dom.window.Element.prototype.attachShadow = function (init) {
    return OriginalAttachShadow.call(this, { ...(init || {}), mode: "open" });
  };
  return dom;
}

function loadOverlayInto(dom) {
  const context = vm.createContext({
    document: dom.window.document,
    window: dom.window,
    sessionStorage: dom.window.sessionStorage,
    history: dom.window.history,
    location: dom.window.location,
  });
  const source = fs.readFileSync(OVERLAY_PATH, "utf8");
  vm.runInContext(source, context, { filename: OVERLAY_PATH });
  return context;
}

function test_renders_and_sets_initial_focus_on_leave_button() {
  const dom = freshDom();
  const context = loadOverlayInto(dom);
  context.window.__phishshieldShowOverlay(91, "HIGH RISK", ["reason one", "reason two"]);

  const host = dom.window.document.getElementById("phishshield-overlay-host");
  assert.ok(host, "overlay host element should be inserted into the document");
  const shadow = host.shadowRoot;
  assert.ok(shadow, "shadow root should be queryable (forced open for this test)");

  const card = shadow.querySelector(".card");
  assert.equal(card.getAttribute("role"), "alertdialog");
  assert.equal(card.getAttribute("aria-modal"), "true");

  const leaveBtn = shadow.querySelector(".leave");
  const continueBtn = shadow.querySelector(".continue");
  assert.equal(leaveBtn.textContent, "Leave website");
  assert.equal(continueBtn.textContent, "Continue anyway");
  assert.equal(shadow.activeElement, leaveBtn, "initial focus should be on the safer 'Leave website' action");

  const reasons = [...shadow.querySelectorAll(".reasons li")].map((li) => li.textContent);
  assert.deepEqual(reasons, ["reason one", "reason two"]);

  const score = shadow.querySelector(".score");
  assert.equal(score.textContent, "91 / 100");
}

function test_tab_focus_trap_wraps_between_the_two_buttons() {
  const dom = freshDom();
  const context = loadOverlayInto(dom);
  context.window.__phishshieldShowOverlay(85, "HIGH RISK", []);
  const shadow = dom.window.document.getElementById("phishshield-overlay-host").shadowRoot;
  const leaveBtn = shadow.querySelector(".leave");
  const continueBtn = shadow.querySelector(".continue");

  continueBtn.focus();
  assert.equal(shadow.activeElement, continueBtn);
  const tabForward = new dom.window.KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
  shadow.dispatchEvent(tabForward);
  assert.equal(shadow.activeElement, leaveBtn, "Tab from the last item should wrap to the first");

  const tabBackward = new dom.window.KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
  shadow.dispatchEvent(tabBackward);
  assert.equal(shadow.activeElement, continueBtn, "Shift+Tab from the first item should wrap to the last");
}

function test_escape_dismisses_the_overlay() {
  const dom = freshDom();
  const context = loadOverlayInto(dom);
  context.window.__phishshieldShowOverlay(77, "HIGH RISK", []);
  const shadow = dom.window.document.getElementById("phishshield-overlay-host").shadowRoot;

  const escEvent = new dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
  shadow.dispatchEvent(escEvent);

  assert.equal(dom.window.document.getElementById("phishshield-overlay-host"), null, "overlay should be removed after Escape");
}

function test_continue_anyway_dismisses_and_is_remembered_for_the_session() {
  const dom = freshDom();
  const context = loadOverlayInto(dom);
  context.window.__phishshieldShowOverlay(66, "HIGH RISK", []);
  let shadow = dom.window.document.getElementById("phishshield-overlay-host").shadowRoot;
  shadow.querySelector(".continue").click();
  assert.equal(dom.window.document.getElementById("phishshield-overlay-host"), null, "overlay should be removed after Continue anyway");

  // Re-invoking with a HIGH verdict in the same session should NOT
  // re-show the warning -- the explicit dismissal is respected until
  // navigation/reload (a fresh JSDOM instance), matching page_overlay.js's
  // documented behavior.
  context.window.__phishshieldShowOverlay(66, "HIGH RISK", []);
  assert.equal(
    dom.window.document.getElementById("phishshield-overlay-host"),
    null,
    "overlay should stay dismissed for the rest of this session"
  );
}

function test_removes_a_previous_overlay_before_showing_a_new_one() {
  const dom = freshDom();
  const context = loadOverlayInto(dom);
  context.window.__phishshieldShowOverlay(60, "HIGH RISK", ["first"]);
  context.window.__phishshieldShowOverlay(95, "HIGH RISK", ["second"]);
  const hosts = dom.window.document.querySelectorAll("#phishshield-overlay-host");
  assert.equal(hosts.length, 1, "only one overlay instance should exist at a time");
  const shadow = hosts[0].shadowRoot;
  assert.equal(shadow.querySelector(".score").textContent, "95 / 100", "the latest verdict should be shown");
}

const tests = [
  test_renders_and_sets_initial_focus_on_leave_button,
  test_tab_focus_trap_wraps_between_the_two_buttons,
  test_escape_dismisses_the_overlay,
  test_continue_anyway_dismisses_and_is_remembered_for_the_session,
  test_removes_a_previous_overlay_before_showing_a_new_one,
];

let failures = 0;
for (const test of tests) {
  try {
    test();
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
