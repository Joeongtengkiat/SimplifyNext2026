const API_BASE = "http://localhost:8000";
const DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const STEP_LABEL = {
  detect_conflicts: "Checked schedule conflicts",
  score_option: "Scored a candidate plan",
};

let currentProposal = null;

function renderSchedule(container, state) {
  const byDay = {};
  for (const day of DAY_ORDER) byDay[day] = [];
  for (const item of state.schedule) {
    if (byDay[item.day]) byDay[item.day].push(item);
  }

  container.innerHTML = DAY_ORDER.filter((d) => byDay[d].length)
    .map((day) => {
      const items = byDay[day]
        .sort((a, b) => a.start.localeCompare(b.start))
        .map(
          (item) => `<div class="sched-item type-${item.type}">
            <span class="time">${item.start}-${item.end}</span>
            <span class="title">${item.title}</span>
          </div>`
        )
        .join("");
      return `<div class="day-group"><div class="day-label">${day}${day === state.today ? " (today)" : ""}</div>${items}</div>`;
    })
    .join("");
}

async function fetchState() {
  const resp = await fetch(`${API_BASE}/state`);
  return resp.json();
}

async function resetState() {
  const resp = await fetch(`${API_BASE}/reset`, { method: "POST" });
  return resp.json();
}

async function injectChange(changeText) {
  const resp = await fetch(`${API_BASE}/inject-change`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ change_text: changeText }),
  });
  if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
  return resp.json();
}

async function executeOption(optionId, proposal) {
  const resp = await fetch(`${API_BASE}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ option_id: optionId, proposal }),
  });
  if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
  return resp.json();
}

async function sendFeedback(optionId, approved, proposal) {
  await fetch(`${API_BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ option_id: optionId, approved, proposal }),
  });
}

function renderSteps(container, steps) {
  container.innerHTML = steps
    .map((s) => `<div class="step"><b>${STEP_LABEL[s.tool] || s.tool}</b> — ${JSON.stringify(s.input)}</div>`)
    .join("");
}

function renderProposal(container, proposal, { onExecuted } = {}) {
  currentProposal = proposal;
  const c = proposal.conflict;

  const conflictHtml = c
    ? `<div class="conflict-summary">
        <div class="stat"><span class="num">${c.remaining_hours}h</span>needed</div>
        <div class="stat"><span class="num">${c.available_hours_before_new_due}h</span>available before ${c.new_due_day}</div>
        <div class="stat"><span class="num">${c.shortfall_hours}h</span>shortfall</div>
      </div>`
    : "";

  const optionsHtml = proposal.options
    .map((opt) => {
      const isRecommended = opt.id === proposal.recommended_option_id;
      const actionsHtml = opt.actions
        .map(
          (a) =>
            `<li><span class="tier-badge tier-${a.tier}">${a.tier}</span> ${describeAction(a)}</li>`
        )
        .join("");
      return `
        <div class="option-card ${isRecommended ? "recommended" : ""}" data-option-id="${opt.id}">
          <div class="option-head">
            <div>${isRecommended ? '<span class="recommended-badge">Recommended</span>' : ""}</div>
            <div class="prob">${Math.round(opt.completion_probability * 100)}%</div>
          </div>
          <div class="option-summary">${opt.summary}</div>
          <button class="why-toggle">WHY?</button>
          <div class="why-box">${opt.breakdown}</div>
          <ul class="action-list">${actionsHtml}</ul>
          <div class="option-actions">
            <button class="execute-btn">Execute adaptation</button>
            <button class="reject-btn secondary">Reject</button>
          </div>
          <div class="execution-result"></div>
        </div>
      `;
    })
    .join("");

  container.innerHTML = `
    <h2>${proposal.change_summary}</h2>
    ${conflictHtml}
    <div class="reasoning">${proposal.reasoning}</div>
    ${optionsHtml}
  `;

  container.querySelectorAll(".why-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.nextElementSibling.classList.toggle("open");
    });
  });

  container.querySelectorAll(".option-card").forEach((card) => {
    const optionId = card.dataset.optionId;

    card.querySelector(".execute-btn").addEventListener("click", async (e) => {
      const btn = e.target;
      btn.disabled = true;
      btn.textContent = "Executing...";
      try {
        const result = await executeOption(optionId, proposal);
        card.querySelector(".execution-result").innerHTML = `
          <ul>${result.results.map((r) => `<li>${r.applied ? "✅" : "🚫"} ${r.detail}</li>`).join("")}</ul>
        `;
        card.querySelectorAll("button").forEach((b) => (b.disabled = true));
        btn.textContent = "Executed";
        if (onExecuted) onExecuted(result.state);
      } catch (err) {
        btn.textContent = "Failed -- try again";
        btn.disabled = false;
      }
    });

    card.querySelector(".reject-btn").addEventListener("click", async (e) => {
      await sendFeedback(optionId, false, proposal);
      e.target.disabled = true;
      e.target.textContent = "Noted";
      card.querySelector(".execute-btn").disabled = true;
    });
  });
}

function describeAction(a) {
  if (a.type === "block_study_time") return `Block ${a.day} ${a.start}-${a.end} for focused work`;
  if (a.type === "move_event") return `Move an item to ${a.to_day}${a.to_start ? " " + a.to_start : ""}`;
  if (a.type === "draft_message") return `Draft a message to ${a.recipient}`;
  return a.type;
}
