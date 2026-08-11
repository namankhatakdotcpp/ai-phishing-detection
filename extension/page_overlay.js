// In-page HIGH-risk warning overlay. Injected via chrome.scripting into
// the active tab only after a HIGH verdict from the same user-invoked
// "Analyze this page" click (activeTab permission -- no automatic/
// background injection). Defines window.__phishshieldShowOverlay(...)
// for popup.js to call with display-only data.
//
// Renders inside a closed Shadow DOM so the host page's CSS can't affect
// it (and vice versa). All dynamic text (risk label, reasons) is set via
// textContent only -- never innerHTML -- so API-derived strings can never
// be interpreted as markup, regardless of what a compromised/malicious
// backend response might contain.

(function () {
  const HOST_ID = "phishshield-overlay-host";
  const DISMISS_KEY = "phishshield_dismissed_this_session";

  function removeExisting() {
    const existing = document.getElementById(HOST_ID);
    if (existing) existing.remove();
  }

  function buildOverlay(riskScore, riskLabel, reasons) {
    const host = document.createElement("div");
    host.id = HOST_ID;
    const shadow = host.attachShadow({ mode: "closed" });

    const style = document.createElement("style");
    style.textContent = `
      .backdrop {
        position: fixed; inset: 0; z-index: 2147483647;
        background: rgba(0, 0, 0, 0.55);
        display: flex; align-items: center; justify-content: center;
        font-family: -apple-system, "Segoe UI", sans-serif;
        animation: fade-in 0.15s ease;
      }
      @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
      .card {
        width: min(420px, 92vw);
        background: #fff;
        border-radius: 14px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.35);
        padding: 28px 26px 22px;
        text-align: center;
        color: #1a1a1a;
      }
      .shield { font-size: 34px; margin-bottom: 4px; }
      .brand { font-size: 12px; font-weight: 700; letter-spacing: 0.05em; color: #a02419; text-transform: uppercase; }
      .headline { font-size: 17px; font-weight: 700; margin: 10px 0 14px; }
      .score { font-size: 40px; font-weight: 800; color: #a02419; line-height: 1; }
      .score-label { font-size: 11px; color: #8a8a8a; margin-bottom: 14px; }
      .bar-track { height: 6px; background: #f0d7d5; border-radius: 3px; overflow: hidden; margin-bottom: 16px; }
      .bar-fill { height: 100%; background: #a02419; border-radius: 3px; }
      .body-text { font-size: 13px; color: #444; margin-bottom: 14px; line-height: 1.4; }
      .reasons { text-align: left; margin: 0 0 18px; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
      .reasons li { font-size: 12px; line-height: 1.4; padding: 8px 10px; background: #fbe1df; border-radius: 6px; border-left: 3px solid #a02419; }
      .actions { display: flex; gap: 10px; }
      button { flex: 1; padding: 11px; font-size: 13px; font-weight: 600; border-radius: 8px; border: none; cursor: pointer; }
      button:focus-visible {
        outline: 3px solid #1a73e8; outline-offset: 2px;
      }
      .leave { background: #a02419; color: #fff; }
      .leave:hover { opacity: 0.9; }
      .continue { background: #f0f0f0; color: #1a1a1a; }
      .continue:hover { background: #e5e5e5; }
      .footer { font-size: 10px; color: #b3b3b3; margin-top: 14px; }
    `;
    shadow.appendChild(style);

    const backdrop = document.createElement("div");
    backdrop.className = "backdrop";

    const card = document.createElement("div");
    card.className = "card";
    // Accessible as a modal alert dialog: labelled by the headline,
    // described by the body text, focus contained within it while shown.
    card.setAttribute("role", "alertdialog");
    card.setAttribute("aria-modal", "true");
    card.setAttribute("aria-labelledby", "phishshield-headline");
    card.setAttribute("aria-describedby", "phishshield-body-text");
    card.tabIndex = -1;

    const shield = document.createElement("div");
    shield.className = "shield";
    shield.textContent = "🛡";
    card.appendChild(shield);

    const brand = document.createElement("div");
    brand.className = "brand";
    brand.textContent = "[PROJECT_NAME]";
    card.appendChild(brand);

    const headline = document.createElement("div");
    headline.id = "phishshield-headline";
    headline.className = "headline";
    headline.textContent = "This website may be dangerous";
    card.appendChild(headline);

    const score = document.createElement("div");
    score.className = "score";
    score.textContent = `${riskScore} / 100`;
    card.appendChild(score);

    const scoreLabel = document.createElement("div");
    scoreLabel.className = "score-label";
    scoreLabel.textContent = riskLabel || "HIGH RISK";
    card.appendChild(scoreLabel);

    const barTrack = document.createElement("div");
    barTrack.className = "bar-track";
    const barFill = document.createElement("div");
    barFill.className = "bar-fill";
    barFill.style.width = `${Math.max(0, Math.min(100, riskScore))}%`;
    barTrack.appendChild(barFill);
    card.appendChild(barTrack);

    const bodyText = document.createElement("div");
    bodyText.id = "phishshield-body-text";
    bodyText.className = "body-text";
    bodyText.textContent =
      "We detected several characteristics commonly associated with phishing websites.";
    card.appendChild(bodyText);

    if (reasons && reasons.length) {
      const ul = document.createElement("ul");
      ul.className = "reasons";
      for (const reason of reasons) {
        const li = document.createElement("li");
        li.textContent = String(reason); // textContent only, never innerHTML
        ul.appendChild(li);
      }
      card.appendChild(ul);
    }

    const actions = document.createElement("div");
    actions.className = "actions";

    const leaveBtn = document.createElement("button");
    leaveBtn.className = "leave";
    leaveBtn.textContent = "Leave website";
    leaveBtn.addEventListener("click", () => {
      if (history.length > 1) {
        history.back();
      } else {
        location.href = "about:blank";
      }
    });

    function dismiss() {
      try {
        sessionStorage.setItem(DISMISS_KEY, "1");
      } catch {
        // sessionStorage unavailable (e.g. sandboxed iframe) -- fine, the
        // overlay is only ever re-shown by another explicit user click.
      }
      host.remove();
    }

    const continueBtn = document.createElement("button");
    continueBtn.className = "continue";
    continueBtn.textContent = "Continue anyway";
    continueBtn.addEventListener("click", dismiss);

    actions.appendChild(leaveBtn);
    actions.appendChild(continueBtn);
    card.appendChild(actions);

    const footer = document.createElement("div");
    footer.className = "footer";
    footer.textContent = "[PROJECT_NAME] -- research prototype, not a guarantee";
    card.appendChild(footer);

    backdrop.appendChild(card);
    shadow.appendChild(backdrop);

    // Keyboard accessibility: Escape dismisses (same as "Continue anyway"
    // -- it does not leave the site, matching how a real dismiss action
    // should behave), and Tab is trapped between the two buttons so
    // keyboard focus can't silently leave the dialog into the page
    // behind it while the warning is showing.
    const focusable = [leaveBtn, continueBtn];
    shadow.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        dismiss();
        return;
      }
      if (event.key === "Tab") {
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && shadow.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && shadow.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    });

    return { host, leaveBtn };
  }

  window.__phishshieldShowOverlay = function (riskScore, riskLabel, reasons) {
    try {
      // Respect an earlier explicit "Continue anyway" for the rest of
      // this tab's session (cleared on navigation/reload) -- re-clicking
      // Analyze shouldn't re-interrupt a choice the user already made.
      // The popup's own risk card still shows the full verdict regardless.
      if (sessionStorage.getItem(DISMISS_KEY) === "1") return;
    } catch {
      // sessionStorage unavailable -- fail open and show the warning.
    }
    removeExisting();
    const { host, leaveBtn } = buildOverlay(riskScore, riskLabel, reasons || []);
    document.documentElement.appendChild(host);
    // Initial focus on the safer action ("Leave website"), matching the
    // convention browsers themselves use for security interstitials --
    // a stray Enter/Space keypress dismisses toward safety, not danger.
    leaveBtn.focus();
  };
})();
