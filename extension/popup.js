// Current-tab analysis: on click, extracts structural features from the
// active tab (via chrome.scripting.executeScript, activeTab permission —
// temporary, user-invoked access only, no background scanning) and POSTs
// only that feature vector to the local PhishShield AI backend. Never
// reads or sends form field values, passwords, or cookies. For a HIGH
// verdict, also injects an in-page warning overlay (page_overlay.js) into
// the same tab, using the same click-granted activeTab access.

// See config.js (loaded before this file in popup.html) -- switch
// PHISHSHIELD_CONFIG.API_BASE there for production, not here.
const API_BASE = PHISHSHIELD_CONFIG.API_BASE;
const REQUEST_TIMEOUT_MS = 10000;

// UI-only labels over the backend's risk_band() ("low"/"medium"/"high") --
// reuses the backend's actual banding, never recomputes it client-side.
const RISK_UI = {
  low: {
    label: "LOW RISK",
    cssClass: "low",
    summary: "No significant phishing indicators detected.",
  },
  medium: {
    label: "SUSPICIOUS",
    cssClass: "suspicious",
    summary: "Some unusual characteristics were detected. This does not necessarily mean the website is malicious -- many legitimate sites trigger some of the same structural signals. Review before entering sensitive information.",
  },
  high: {
    label: "HIGH RISK",
    cssClass: "high",
    summary: "Strong phishing indicators were detected. We recommend leaving this website.",
  },
};

const pageInfoEl = document.getElementById("page-info");
const analyzeBtn = document.getElementById("analyze-btn");
const statusEl = document.getElementById("status");
const analyzingEl = document.getElementById("analyzing");
const errorStateEl = document.getElementById("error-state");
const errorMessageEl = document.getElementById("error-message");
const retryBtn = document.getElementById("retry-btn");
const resultEl = document.getElementById("result");
const riskCardEl = document.getElementById("risk-card");
const riskLabelEl = document.getElementById("risk-label");
const riskScoreEl = document.getElementById("risk-score");
const riskSummaryEl = document.getElementById("risk-summary");
const reasonsSectionEl = document.getElementById("reasons-section");
const reasonsEl = document.getElementById("reasons");
const highRiskActionsEl = document.getElementById("high-risk-actions");
const leaveBtn = document.getElementById("leave-btn");
const continueBtn = document.getElementById("continue-btn");
const detailsToggle = document.getElementById("details-toggle");
const detailsEl = document.getElementById("details");
const classifierScoreEl = document.getElementById("classifier-score");
const judgeScoreEl = document.getElementById("judge-score");
const analyzedAtEl = document.getElementById("analyzed-at");

let activeTabId = null;

function setStatus(message) {
  statusEl.textContent = message || "";
}

function setState(state) {
  analyzingEl.classList.toggle("hidden", state !== "analyzing");
  errorStateEl.classList.toggle("hidden", state !== "error");
  resultEl.classList.toggle("hidden", state !== "result");
}

// Explicit, distinguishable failure states -- never shows a fake/default
// risk score on failure (setState("error") hides the result section
// entirely). Each branch names the actual failure mode rather than one
// generic "something went wrong" message.
function showError(message) {
  errorMessageEl.textContent = message;
  setState("error");
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function isAnalyzablePage(url) {
  return typeof url === "string" && /^https?:\/\//.test(url);
}

async function showActiveTabInfo() {
  const tab = await getActiveTab();
  if (!tab || !isAnalyzablePage(tab.url)) {
    pageInfoEl.textContent = "This page can't be analyzed (not http/https).";
    analyzeBtn.disabled = true;
    return;
  }
  activeTabId = tab.id;
  pageInfoEl.textContent = tab.url;
  analyzeBtn.disabled = false;
}

async function extractFeaturesFromTab(tabId) {
  const [injection] = await chrome.scripting.executeScript({
    target: { tabId },
    files: ["page_extractor.js"],
  });
  return injection.result;
}

async function injectWarningOverlay(tabId, verdict) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["page_overlay.js"],
    });
    // page_overlay.js defines window.__phishshieldShowOverlay -- call it
    // with only the display data the overlay needs (never raw feature
    // internals), each value passed as a plain, already-safe argument
    // (executeScript args are structured-cloned, not stringified into
    // code, so this isn't vulnerable to injection via reason text).
    await chrome.scripting.executeScript({
      target: { tabId },
      func: (riskScore, riskLabel, reasons) => {
        if (window.__phishshieldShowOverlay) {
          window.__phishshieldShowOverlay(riskScore, riskLabel, reasons);
        }
      },
      args: [verdict.risk_score, RISK_UI[verdict.risk_band]?.label || "HIGH RISK", verdict.reasons],
    });
  } catch (err) {
    // Restricted page (chrome://, Web Store, etc.) or injection failed --
    // the popup result still shows the full verdict either way.
  }
}

async function fetchAnalysis(features, url, title) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ features, url, title }),
      signal: controller.signal,
    });
  } catch (err) {
    if (err.name === "AbortError") {
      throw new AnalysisError(
        "timeout",
        `The backend didn't respond within ${REQUEST_TIMEOUT_MS / 1000} seconds. It may be slow, overloaded, or unreachable.`
      );
    }
    // fetch() rejects with a generic TypeError for DNS/connection failures
    // -- this is the "backend isn't running / can't be reached" case.
    throw new AnalysisError(
      "offline",
      `Couldn't reach the PhishShield backend at ${API_BASE}. ` +
        `Is it running? (uvicorn phishshield.api.app:app --port 8000)`
    );
  } finally {
    clearTimeout(timeoutId);
  }

  if (response.status === 503) {
    let detail = "The backend is running but its model isn't loaded.";
    try {
      const body = await response.json();
      if (body && body.detail) detail = body.detail;
    } catch {
      // fall through to the default detail text above
    }
    throw new AnalysisError("model_unavailable", detail);
  }
  if (response.status === 429) {
    throw new AnalysisError("rate_limited", "Too many requests -- please wait a moment and try again.");
  }
  if (response.status >= 500) {
    throw new AnalysisError("server_error", `Backend error (HTTP ${response.status}). Try again in a moment.`);
  }
  if (!response.ok) {
    throw new AnalysisError(
      "rejected",
      `The backend rejected this request (HTTP ${response.status}). This shouldn't normally happen.`
    );
  }

  let verdict;
  try {
    verdict = await response.json();
  } catch {
    throw new AnalysisError("malformed_response", "Got a response the extension couldn't understand (invalid JSON).");
  }
  if (
    typeof verdict.risk_score !== "number" ||
    typeof verdict.risk_band !== "string" ||
    !Array.isArray(verdict.reasons)
  ) {
    throw new AnalysisError("malformed_response", "Got an unexpected response shape from the backend.");
  }
  return verdict;
}

class AnalysisError extends Error {
  constructor(kind, message) {
    super(message);
    this.kind = kind;
  }
}

async function analyzeCurrentPage() {
  analyzeBtn.disabled = true;
  setStatus("");
  setState("analyzing");

  try {
    const tab = await getActiveTab();
    if (!tab || !isAnalyzablePage(tab.url)) {
      showError("This page can't be analyzed (not an http:// or https:// page).");
      return;
    }

    const rawFeatures = await extractFeaturesFromTab(tab.id);
    if (!rawFeatures) {
      showError("Couldn't read this page (restricted page, e.g. chrome:// or the Web Store, or the extension was blocked here).");
      return;
    }

    // Strip display-only metadata before sending -- the backend's feature
    // schema is numeric-only; page URL/title are for the popup UI, never
    // used as a model feature or logged.
    const { _meta_url, _meta_title, ...features } = rawFeatures;

    const verdict = await fetchAnalysis(features, _meta_url, _meta_title);
    renderResult(verdict, tab.id);
  } catch (err) {
    // Never falls through to showing a risk score on failure -- setState
    // inside showError hides the result section entirely.
    showError(err instanceof AnalysisError ? err.message : "An unexpected error occurred while analyzing this page.");
  } finally {
    analyzeBtn.disabled = false;
  }
}

function renderResult(verdict, tabId) {
  const ui = RISK_UI[verdict.risk_band] || RISK_UI.high;

  riskCardEl.className = `risk-card ${ui.cssClass}`;
  riskLabelEl.textContent = ui.label;
  riskScoreEl.textContent = `${verdict.risk_score} / 100`;
  riskSummaryEl.textContent = ui.summary;

  const isHigh = verdict.risk_band === "high";
  reasonsSectionEl.classList.toggle("hidden", verdict.reasons.length === 0 || !isHigh);
  reasonsEl.innerHTML = "";
  if (isHigh) {
    for (const reason of verdict.reasons) {
      const li = document.createElement("li");
      li.textContent = reason; // textContent only -- never innerHTML of API-derived text
      reasonsEl.appendChild(li);
    }
  }

  highRiskActionsEl.classList.toggle("hidden", !isHigh);

  classifierScoreEl.textContent = `classifier: ${(verdict.classifier_score * 100).toFixed(1)}%`;
  judgeScoreEl.textContent = `judge: ${(verdict.judge_score * 100).toFixed(1)}%`;
  analyzedAtEl.textContent = verdict.model_version
    ? `Analyzed just now (model ${verdict.model_version})`
    : "Analyzed just now";

  setState("result");

  if (isHigh && tabId != null) {
    injectWarningOverlay(tabId, verdict);
  }
}

async function leaveWebsite() {
  if (activeTabId == null) return;
  try {
    await chrome.tabs.goBack(activeTabId);
  } catch {
    await chrome.tabs.update(activeTabId, { url: "about:blank" });
  }
  window.close();
}

detailsToggle.addEventListener("click", () => {
  detailsEl.classList.toggle("hidden");
});
leaveBtn.addEventListener("click", leaveWebsite);
continueBtn.addEventListener("click", () => window.close());
analyzeBtn.addEventListener("click", analyzeCurrentPage);
retryBtn.addEventListener("click", analyzeCurrentPage);

showActiveTabInfo();
