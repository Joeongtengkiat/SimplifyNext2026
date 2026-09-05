const API_BASE = "http://localhost:8000";
const DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const STEP_LABEL = { detect_conflicts: "Checked schedule conflicts", score_option: "Scored a candidate plan", find_free_slots: "Checked free time" };

// ---------------------------------------------------------------------------------------------
// The seed data only knows "Mon".."Sun" (day-of-week labels, no real dates) -- to show a real
// Day/Month/Year calendar we anchor those labels to the current real-world week. This is
// deliberate, not a hack: only that one week has data, same as any fresh calendar app.
// ---------------------------------------------------------------------------------------------

function stripTime(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function getAnchorMonday() {
  const now = stripTime(new Date());
  const day = now.getDay(); // 0=Sun..6=Sat
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(now);
  monday.setDate(now.getDate() + diffToMonday);
  return monday;
}

const ANCHOR_MONDAY = getAnchorMonday();

function dayLabelToDate(label) {
  const idx = DAY_ORDER.indexOf(label);
  const d = new Date(ANCHOR_MONDAY);
  d.setDate(ANCHOR_MONDAY.getDate() + idx);
  return d;
}

function dateToDayLabel(date) {
  const diffDays = Math.round((stripTime(date) - ANCHOR_MONDAY) / 86400000);
  return diffDays >= 0 && diffDays < 7 ? DAY_ORDER[diffDays] : null;
}

function fmtDate(date) {
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function itemsForDate(state, date) {
  const label = dateToDayLabel(date);
  if (!label) return [];
  return state.schedule.filter((i) => i.day === label).sort((a, b) => a.start.localeCompare(b.start));
}

// ---------------------------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------------------------

async function fetchState() {
  return (await fetch(`${API_BASE}/state`)).json();
}

async function resetState() {
  return (await fetch(`${API_BASE}/reset`, { method: "POST" })).json();
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

async function scheduleEvent(day, start, end, title, type) {
  const resp = await fetch(`${API_BASE}/schedule-event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ day, start, end, title, type }),
  });
  if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
  return resp.json();
}

// ---------------------------------------------------------------------------------------------
// Category colors -- the backend assigns each event a topic (academic/career/social/health/
// personal/other, see backend/categorize.py); color is purely a display preference, so it's
// owned entirely client-side and persisted in localStorage rather than round-tripping to the
// server just to change a swatch.
// ---------------------------------------------------------------------------------------------

const DEFAULT_CATEGORY_COLORS = {
  academic: "#3b82f6", // blue
  career: "#dc2626", // red
  social: "#a855f7", // purple
  health: "#16a34a", // green
  personal: "#f59e0b", // amber
  other: "#6b7280", // gray
};
const CATEGORY_COLORS_KEY = "adapt_category_colors";

function getCategoryColors() {
  try {
    const stored = JSON.parse(localStorage.getItem(CATEGORY_COLORS_KEY) || "{}");
    return { ...DEFAULT_CATEGORY_COLORS, ...stored };
  } catch {
    return { ...DEFAULT_CATEGORY_COLORS };
  }
}

function setCategoryColor(category, hex) {
  const colors = getCategoryColors();
  colors[category] = hex;
  try {
    localStorage.setItem(CATEGORY_COLORS_KEY, JSON.stringify(colors));
  } catch {
    // private-browsing / storage-blocked -- the color just won't persist across reloads
  }
}

function categoryColor(category) {
  const colors = getCategoryColors();
  return colors[category] || colors.other;
}

function renderCategoryLegend(container, state) {
  const categoriesInUse = [...new Set(state.schedule.map((i) => i.category || "other"))].sort();
  container.innerHTML = categoriesInUse
    .map(
      (cat) => `<label class="legend-swatch">
        <input type="color" data-cat="${cat}" value="${categoryColor(cat)}" />
        <span>${cat}</span>
      </label>`
    )
    .join("");

  container.querySelectorAll('input[type="color"]').forEach((input) => {
    input.addEventListener("input", () => {
      setCategoryColor(input.dataset.cat, input.value);
      renderCurrentView();
    });
  });
}

// ---------------------------------------------------------------------------------------------
// Calendar views
// ---------------------------------------------------------------------------------------------

function itemBlockHtml(item) {
  const color = categoryColor(item.category || "other");
  return `<div class="sched-item" style="border-left-color: ${color}">
    <span class="time">${item.start}-${item.end}</span>
    <span class="title">${item.title}</span>
  </div>`;
}

const DAY_TIMELINE_START_HOUR = 7; // matches the backend's find_free_slots waking window (07:00-23:00)
const DAY_TIMELINE_END_HOUR = 23;
const DAY_TIMELINE_PX_PER_HOUR = 48;

function timeToTimelineOffset(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return (h - DAY_TIMELINE_START_HOUR) * DAY_TIMELINE_PX_PER_HOUR + (m / 60) * DAY_TIMELINE_PX_PER_HOUR;
}

function renderDayView(container, state, date) {
  const items = itemsForDate(state, date);
  const totalHeight = (DAY_TIMELINE_END_HOUR - DAY_TIMELINE_START_HOUR) * DAY_TIMELINE_PX_PER_HOUR;

  const hourLabels = [];
  for (let h = DAY_TIMELINE_START_HOUR; h <= DAY_TIMELINE_END_HOUR; h++) {
    const top = (h - DAY_TIMELINE_START_HOUR) * DAY_TIMELINE_PX_PER_HOUR;
    hourLabels.push(`<div class="hour-label" style="top: ${top}px">${String(h).padStart(2, "0")}:00</div>`);
  }

  const blocks = items
    .map((item) => {
      const top = timeToTimelineOffset(item.start);
      const height = Math.max(22, timeToTimelineOffset(item.end) - top);
      const color = categoryColor(item.category || "other");
      return `<div class="timeline-block" style="top: ${top}px; height: ${height}px; border-left-color: ${color}">
        <div class="timeline-block-title">${item.title}</div>
        <div class="timeline-block-time">${item.start}-${item.end}</div>
      </div>`;
    })
    .join("");

  const isToday = stripTime(date).getTime() === stripTime(new Date()).getTime();
  const now = new Date();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const nowInWindow = nowMinutes >= DAY_TIMELINE_START_HOUR * 60 && nowMinutes <= DAY_TIMELINE_END_HOUR * 60;
  const nowLine =
    isToday && nowInWindow
      ? `<div class="now-line" style="top: ${((nowMinutes - DAY_TIMELINE_START_HOUR * 60) / 60) * DAY_TIMELINE_PX_PER_HOUR}px"></div>`
      : "";

  container.innerHTML = `
    <div class="cal-day-label">${fmtDate(date)}</div>
    <div class="day-timeline-wrap" style="height: ${totalHeight}px">
      ${hourLabels.join("")}
      <div class="day-timeline" style="height: ${totalHeight}px">
        ${blocks}
        ${nowLine}
      </div>
    </div>
    ${items.length ? "" : '<div class="empty-note">Nothing scheduled.</div>'}
  `;
}

function renderWeekView(container, state, startDate) {
  const cols = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startDate);
    d.setDate(startDate.getDate() + i);
    const items = itemsForDate(state, d);
    return `<div class="week-col">
      <div class="week-col-label">${d.toLocaleDateString(undefined, { weekday: "short" })}<br/><span>${d.getDate()}</span></div>
      ${items.map(itemBlockHtml).join("")}
    </div>`;
  }).join("");
  container.innerHTML = `<div class="week-grid">${cols}</div>`;
}

function renderMonthView(container, state, monthDate) {
  const year = monthDate.getFullYear();
  const month = monthDate.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // Monday-first grid
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  let cells = "";
  for (let i = 0; i < startOffset; i++) cells += `<div class="month-cell empty"></div>`;
  for (let day = 1; day <= daysInMonth; day++) {
    const d = new Date(year, month, day);
    const items = itemsForDate(state, d);
    const isToday = stripTime(d).getTime() === stripTime(new Date()).getTime();
    cells += `<div class="month-cell ${isToday ? "today" : ""}">
      <div class="month-cell-num">${day}</div>
      ${items.slice(0, 2).map((i) => `<div class="month-dot" style="background: ${categoryColor(i.category || "other")}" title="${i.title}">${i.title}</div>`).join("")}
      ${items.length > 2 ? `<div class="month-more">+${items.length - 2} more</div>` : ""}
    </div>`;
  }

  container.innerHTML = `
    <div class="cal-title">${MONTH_NAMES[month]} ${year}</div>
    <div class="month-grid-header">${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d) => `<div>${d}</div>`).join("")}</div>
    <div class="month-grid">${cells}</div>
  `;
}

function renderYearView(container, state, year) {
  let months = "";
  for (let m = 0; m < 12; m++) {
    const firstOfMonth = new Date(year, m, 1);
    const startOffset = (firstOfMonth.getDay() + 6) % 7;
    const daysInMonth = new Date(year, m + 1, 0).getDate();
    let cells = "";
    for (let i = 0; i < startOffset; i++) cells += `<div class="mini-cell empty"></div>`;
    for (let day = 1; day <= daysInMonth; day++) {
      const d = new Date(year, m, day);
      const hasItems = itemsForDate(state, d).length > 0;
      cells += `<div class="mini-cell ${hasItems ? "has-events" : ""}">${day}</div>`;
    }
    months += `<div class="mini-month"><div class="mini-month-title">${MONTH_NAMES[m]}</div><div class="mini-grid">${cells}</div></div>`;
  }
  container.innerHTML = `<div class="cal-title">${year}</div><div class="year-grid">${months}</div>`;
}

function renderRangeView(container, state, startDate, endDate) {
  const days = [];
  const cursor = new Date(startDate);
  while (cursor <= endDate && days.length < 31) {
    days.push(new Date(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  const rows = days
    .map((d) => {
      const items = itemsForDate(state, d);
      return `<div class="day-group"><div class="day-label">${fmtDate(d)}</div>${
        items.length ? items.map(itemBlockHtml).join("") : '<div class="empty-note">Nothing scheduled.</div>'
      }</div>`;
    })
    .join("");
  container.innerHTML = rows || '<div class="empty-note">Pick a valid range.</div>';
}

// ---------------------------------------------------------------------------------------------
// Reasoning trace + adaptation proposal (unchanged behavior, same as before)
// ---------------------------------------------------------------------------------------------

function renderSteps(container, steps) {
  container.innerHTML = steps
    .map((s) => `<div class="step"><b>${STEP_LABEL[s.tool] || s.tool}</b> — ${JSON.stringify(s.input)}</div>`)
    .join("");
}

function describeAction(a) {
  if (a.type === "block_study_time") return `Block ${a.day} ${a.start}-${a.end} for focused work`;
  if (a.type === "move_event") return `Move an item to ${a.to_day}${a.to_start ? " " + a.to_start : ""}`;
  if (a.type === "draft_message") return `Draft a message to ${a.recipient}`;
  return a.type;
}

function renderProposal(container, proposal, { onExecuted } = {}) {
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
        .map((a) => `<li><span class="tier-badge tier-${a.tier}">${a.tier}</span> ${describeAction(a)}</li>`)
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

  container.innerHTML = `<h2>${proposal.change_summary}</h2>${conflictHtml}<div class="reasoning">${proposal.reasoning}</div>${optionsHtml}`;

  container.querySelectorAll(".why-toggle").forEach((btn) => {
    btn.addEventListener("click", () => btn.nextElementSibling.classList.toggle("open"));
  });

  container.querySelectorAll(".option-card").forEach((card) => {
    const optionId = card.dataset.optionId;

    card.querySelector(".execute-btn").addEventListener("click", async (e) => {
      const btn = e.target;
      btn.disabled = true;
      btn.textContent = "Executing...";
      try {
        const result = await executeOption(optionId, proposal);
        card.querySelector(".execution-result").innerHTML = `<ul>${result.results
          .map((r) => `<li>${r.applied ? "✅" : "🚫"} ${r.detail}</li>`)
          .join("")}</ul>`;
        card.querySelectorAll("button").forEach((b) => (b.disabled = true));
        btn.textContent = "Executed";
        if (onExecuted) onExecuted(result.state);
      } catch {
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

// ---------------------------------------------------------------------------------------------
// Availability query + slot picker -- rendered inline inside a chat bubble
// ---------------------------------------------------------------------------------------------

function renderSlotPicker(container, queryResponse, { onScheduled } = {}) {
  const slots = queryResponse.free_slots;

  const slotCards = slots
    .map(
      (s, i) => `<div class="slot-card" data-idx="${i}">
        <div class="slot-day">${s.day}</div>
        <div class="slot-time">${s.start} - ${s.end}</div>
        <div class="slot-duration">${s.duration_hours}h free</div>
      </div>`
    )
    .join("");

  const recommendedHtml = queryResponse.recommended_slot
    ? `<div class="recommended-note">💡 Recommended: <b>${queryResponse.recommended_slot.day} ${queryResponse.recommended_slot.start}-${queryResponse.recommended_slot.end}</b> — ${queryResponse.recommended_slot.reasoning}</div>`
    : "";

  container.innerHTML = `
    <p>${queryResponse.message}</p>
    ${recommendedHtml}
    <div class="slot-grid">${slotCards || '<div class="empty-note">No free slots matched.</div>'}</div>
    <div class="slot-editor" style="display: none;"></div>
  `;

  container.querySelectorAll(".slot-card").forEach((card) => {
    card.addEventListener("click", () => {
      container.querySelectorAll(".slot-card").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
      const slot = slots[parseInt(card.dataset.idx, 10)];
      renderSlotEditor(container.querySelector(".slot-editor"), slot, onScheduled);
    });
  });
}

function renderSlotEditor(container, slot, onScheduled) {
  container.style.display = "block";
  container.innerHTML = `
    <div class="slot-editor-form">
      <label>Day <input type="text" id="ed-day" value="${slot.day}" readonly /></label>
      <label>Start <input type="time" id="ed-start" value="${slot.start}" /></label>
      <label>End <input type="time" id="ed-end" value="${slot.end}" /></label>
      <label>Title <input type="text" id="ed-title" placeholder="What is this?" /></label>
      <button id="ed-confirm">Add to calendar</button>
      <div id="ed-status"></div>
    </div>
  `;

  container.querySelector("#ed-confirm").addEventListener("click", async () => {
    const day = container.querySelector("#ed-day").value;
    const start = container.querySelector("#ed-start").value;
    const end = container.querySelector("#ed-end").value;
    const title = container.querySelector("#ed-title").value.trim() || "Untitled";
    const statusEl = container.querySelector("#ed-status");
    const confirmBtn = container.querySelector("#ed-confirm");

    try {
      const state = await scheduleEvent(day, start, end, title, "personal");
      statusEl.textContent = "Added to calendar.";
      confirmBtn.disabled = true;
      if (onScheduled) onScheduled(state);
    } catch (err) {
      statusEl.textContent = `Failed: ${err.message}`;
    }
  });
}
