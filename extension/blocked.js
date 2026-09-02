const API_BASE = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", async () => {
  const domainEl = document.getElementById("domain");
  const explanationEl = document.getElementById("explanation");
  const evidenceEl = document.getElementById("evidence");
  const statusEl = document.getElementById("status");
  const goBackBtn = document.getElementById("go-back");
  const trustBtn = document.getElementById("trust");
  const proceedBtn = document.getElementById("proceed");

  const tab = await chrome.tabs.getCurrent();
  const tabId = tab.id;
  const storageKey = `block:${tabId}`;
  const { [storageKey]: block } = await chrome.storage.session.get(storageKey);

  if (!block) {
    // opened directly / storage already cleared -- nothing to show, safest default is to just
    // not display a fabricated warning
    domainEl.textContent = "(no details available)";
    explanationEl.textContent = "This page was opened without an active investigation result.";
    goBackBtn.style.display = "none";
    trustBtn.style.display = "none";
    proceedBtn.style.display = "none";
    return;
  }

  domainEl.textContent = block.domain || new URL(block.url).hostname;
  explanationEl.textContent = block.verdict.explanation;
  evidenceEl.innerHTML = block.verdict.evidence
    .map((e) => `<li><b>${e.signal}:</b> ${e.detail}</li>`)
    .join("");

  goBackBtn.addEventListener("click", () => {
    if (history.length > 1) {
      history.back();
    } else {
      chrome.tabs.update(tabId, { url: "about:blank" });
    }
  });

  trustBtn.addEventListener("click", async () => {
    trustBtn.disabled = true;
    trustBtn.textContent = "Trusting...";
    try {
      const resp = await fetch(`${API_BASE}/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: `-trust ${block.domain}` }),
      });
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
      await chrome.storage.session.set({ [`cleared:${block.domain}`]: true });
      statusEl.textContent = `${block.domain} added to the trusted list. Proceeding...`;
      chrome.tabs.update(tabId, { url: block.url });
    } catch (err) {
      statusEl.textContent = `Couldn't trust the domain: ${err.message}`;
      trustBtn.disabled = false;
      trustBtn.textContent = "This is a mistake — trust this domain";
    }
  });

  proceedBtn.addEventListener("click", async () => {
    // session-only bypass: don't re-block this domain again this browser session, but don't
    // add it to the permanent trusted list either -- that's what the Trust button is for
    await chrome.storage.session.set({ [`cleared:${block.domain}`]: true });
    chrome.tabs.update(tabId, { url: block.url });
  });
});
