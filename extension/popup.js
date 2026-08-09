// Demo-only UI: talks exclusively to the local PhishShield AI backend and
// only ever scores one of the curated demo samples returned by
// GET /demo-samples. It never reads the current tab's URL or content —
// this extension has no host_permissions or activeTab/scripting grant for
// that, on purpose (see PROJECT_BRIEF.md, Phase 6).

const API_BASE = "http://127.0.0.1:8000";

const selectEl = document.getElementById("sample-select");
const analyzeBtn = document.getElementById("analyze-btn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const riskScoreEl = document.getElementById("risk-score");
const riskBandEl = document.getElementById("risk-band");
const reasonsEl = document.getElementById("reasons");
const classifierScoreEl = document.getElementById("classifier-score");
const judgeScoreEl = document.getElementById("judge-score");

function setStatus(message) {
  statusEl.textContent = message || "";
}

async function loadDemoSamples() {
  setStatus("Loading demo samples…");
  analyzeBtn.disabled = true;
  try {
    const response = await fetch(`${API_BASE}/demo-samples`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const samples = await response.json();

    selectEl.innerHTML = "";
    for (const sample of samples) {
      const option = document.createElement("option");
      option.value = sample.id;
      option.textContent = sample.display_name;
      selectEl.appendChild(option);
    }
    analyzeBtn.disabled = samples.length === 0;
    setStatus("");
  } catch (err) {
    setStatus(
      `Couldn't reach the PhishShield backend at ${API_BASE}. ` +
        `Is it running? (uvicorn phishshield.api.app:app --port 8000)`
    );
  }
}

async function analyzeSelectedSample() {
  const sampleId = selectEl.value;
  if (!sampleId) return;

  analyzeBtn.disabled = true;
  setStatus("Analyzing…");
  resultEl.classList.add("hidden");

  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sample_id: sampleId }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const verdict = await response.json();
    renderResult(verdict);
    setStatus("");
  } catch (err) {
    setStatus("Analysis failed — is the backend running?");
  } finally {
    analyzeBtn.disabled = false;
  }
}

function renderResult(verdict) {
  riskScoreEl.textContent = `Risk Score: ${verdict.risk_score}%`;
  riskBandEl.textContent = verdict.risk_band;
  riskBandEl.className = `risk-band ${verdict.risk_band}`;

  reasonsEl.innerHTML = "";
  for (const reason of verdict.reasons) {
    const li = document.createElement("li");
    li.textContent = reason;
    reasonsEl.appendChild(li);
  }

  classifierScoreEl.textContent = `classifier: ${(verdict.classifier_score * 100).toFixed(1)}%`;
  judgeScoreEl.textContent = `judge: ${(verdict.judge_score * 100).toFixed(1)}%`;

  resultEl.classList.remove("hidden");
}

analyzeBtn.addEventListener("click", analyzeSelectedSample);
loadDemoSamples();
