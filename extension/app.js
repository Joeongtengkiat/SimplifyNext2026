const API_BASE = "http://localhost:8000";

const TOOL_ICONS = {
  check_domain: "\u{1F4C7}", // card index
  fetch_url: "\u{1F310}", // globe
  web_search: "\u{1F50D}", // magnifying glass
  check_allowlist: "✅", // check mark
};

const VERDICT_ICONS = {
  likely_legitimate: "✅",
  suspicious: "⚠️",
  likely_phishing: "\u{1F6A8}",
};

function renderSteps(container, steps) {
  container.innerHTML = steps
    .map((s) => {
      const icon = TOOL_ICONS[s.tool] || "\u{1F6E0}️";
      const inputSummary = Object.values(s.input || {}).join(", ");
      return `<div class="step">
        <span class="icon">${icon}</span>
        <span class="tool-name">${s.tool}</span>
        <span class="tool-input">${inputSummary}</span>
      </div>`;
    })
    .join("");
}

function renderVerdict(container, data) {
  const v = data.verdict;
  const icon = VERDICT_ICONS[v.verdict] || "❓";
  const alreadyTrusted = v.evidence.some((e) => e.signal === "trusted_allowlist");

  const evidenceHtml = v.evidence.length
    ? `<ul class="evidence-list">${v.evidence
        .map((e) => `<li><b>${e.signal}:</b> ${e.detail}</li>`)
        .join("")}</ul>`
    : "";
  const warningsHtml = data.warnings && data.warnings.length
    ? `<div class="warnings">Note: ${data.warnings.join(" • ")}</div>`
    : "";
  const trustButtonHtml = !data.domain
    ? ""
    : alreadyTrusted
    ? `<span class="trust-btn trusted">✓ Already trusted</span>`
    : `<button class="trust-btn" data-domain="${data.domain}">Trust ${data.domain}</button>`;

  container.innerHTML = `
    <div class="verdict-card ${v.verdict}">
      <div class="verdict-head">
        <span class="verdict-icon">${icon}</span>
        <span class="verdict-title">${v.verdict.replace(/_/g, " ")}</span>
        <span class="confidence-pill">${v.confidence} confidence</span>
      </div>
      <p class="explanation">${v.explanation}</p>
      ${evidenceHtml}
      ${warningsHtml}
      <div class="verdict-footer">
        <span class="meta">${v.investigation_steps} investigation step(s) taken</span>
        ${trustButtonHtml}
      </div>
    </div>
  `;

  const trustBtn = container.querySelector("button.trust-btn");
  if (trustBtn) {
    trustBtn.addEventListener("click", async () => {
      const domain = trustBtn.dataset.domain;
      trustBtn.disabled = true;
      trustBtn.textContent = "Trusting...";
      try {
        await investigate(`-trust ${domain}`);
        trustBtn.textContent = `✓ Trusted ${domain}`;
        trustBtn.classList.add("trusted");
      } catch {
        trustBtn.textContent = "Trust failed -- try again";
        trustBtn.disabled = false;
      }
    });
  }
}

async function investigate(input) {
  const resp = await fetch(`${API_BASE}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
  if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
  return resp.json();
}

function wireUpForm({ inputEl, submitEl, statusEl, stepsEl, verdictEl }) {
  submitEl.addEventListener("click", async () => {
    const text = inputEl.value.trim();
    if (!text) return;

    stepsEl.innerHTML = "";
    verdictEl.innerHTML = "";
    statusEl.className = "";
    statusEl.innerHTML = `<span class="spinner"></span>Investigating...`;
    submitEl.disabled = true;

    try {
      const data = await investigate(text);

      if (data.command === "trust") {
        statusEl.className = data.error ? "error" : "";
        statusEl.textContent = data.error || data.message;
        return;
      }

      statusEl.textContent = "";
      renderSteps(stepsEl, data.steps);
      renderVerdict(verdictEl, data);
    } catch (err) {
      statusEl.className = "error";
      statusEl.textContent = `Error: ${err.message}. Is the backend running (uvicorn backend.main:app)?`;
    } finally {
      submitEl.disabled = false;
    }
  });
}
