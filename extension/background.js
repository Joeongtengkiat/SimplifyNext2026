const API_BASE = "http://localhost:8000";

const MENU_ID_LINK = "phishtrace-investigate-link";
const MENU_ID_PAGE = "phishtrace-investigate-page";

const VERDICT_LABEL = {
  likely_legitimate: "Looks legitimate",
  suspicious: "Suspicious",
  likely_phishing: "Likely phishing",
};

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_ID_LINK,
    title: "Investigate this link with PhishTrace",
    contexts: ["link"],
  });
  chrome.contextMenus.create({
    id: MENU_ID_PAGE,
    title: "Investigate this page with PhishTrace",
    contexts: ["page"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  const target = info.menuItemId === MENU_ID_LINK ? info.linkUrl : info.pageUrl;
  if (!target) return;

  // also stash it so opening the popup right after shows the full step-by-step trace,
  // not just the notification summary
  chrome.storage.local.set({ prefillInput: target });

  try {
    const resp = await fetch(`${API_BASE}/investigate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: target }),
    });
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
    const data = await resp.json();
    notifyResult(target, data);
  } catch (err) {
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "PhishTrace couldn't investigate",
      message: `${err.message}. Is the backend running (uvicorn backend.main:app)?`,
    });
  }
});

function notifyResult(target, data) {
  if (data.command === "trust") return; // context menu never sends -trust input, but be safe

  const v = data.verdict;
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: `${VERDICT_LABEL[v.verdict] || v.verdict} (${v.confidence} confidence)`,
    message: v.explanation,
    contextMessage: target,
  });
}
