// Current-tab analysis: on click, extracts structural features from the
// active tab (via chrome.scripting.executeScript, activeTab permission —
// temporary, user-invoked access only, no background scanning) and POSTs
// only that feature vector to the local PhishShield AI backend. Never
// reads or sends form field values, passwords, or cookies. For a HIGH
// verdict, also injects an in-page warning overlay (page_overlay.js) into
// the same tab, using the same click-granted activeTab access.

const API_BASE = "http://127.0.0.1:8000";

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
    summary: "This website contains some unusual characteristics. Review before entering sensitive information.",
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
  resultEl.classList.toggle("hidden", state !== "result");
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

async function analyzeCurrentPage() {
  analyzeBtn.disabled = true;
  setStatus("");
  setState("analyzing");

  try {
    const tab = await getActiveTab();
    if (!tab || !isAnalyzablePage(tab.url)) {
      setState(null);
      setStatus("This page can't be analyzed.");
      return;
    }

    const rawFeatures = await extractFeaturesFromTab(tab.id);
    if (!rawFeatures) {
      setState(null);
      setStatus("Couldn't read this page (restricted page or extension blocked here).");
      return;
    }

    // Strip display-only metadata before sending -- the backend's feature
    // schema is numeric-only; page URL/title are for the popup UI, never
    // used as a model feature or logged.
    const { _meta_url, _meta_title, ...features } = rawFeatures;

    const response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ features, url: _meta_url, title: _meta_title }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const verdict = await response.json();
    renderResult(verdict, tab.id);
  } catch (err) {
    setState(null);
    setStatus(
      `Couldn't reach the PhishShield backend at ${API_BASE}. ` +
        `Is it running? (uvicorn phishshield.api.app:app --port 8000)`
    );
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
  analyzedAtEl.textContent = `Analyzed just now`;

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

showActiveTabInfo();
