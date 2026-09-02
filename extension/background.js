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
    const data = await callBackend(target);
    notifyResult(target, data);
  } catch (err) {
    notifyError(err);
  }
});

async function callBackend(input) {
  const resp = await fetch(`${API_BASE}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
  if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
  return resp.json();
}

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

function notifyError(err) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: "PhishTrace couldn't investigate",
    message: `${err.message}. Is the backend running (uvicorn backend.main:app)?`,
  });
}

// ---------------------------------------------------------------------------------------------
// Auto-protect: check new sites as the user navigates to them, and redirect away from ones
// that come back "likely_phishing". Off by default (toggled in the popup) since it means a real
// Bedrock call for every new domain visited -- real time and real AWS budget.
//
// Manifest V3 has no synchronous network blocking, so this can't be a true pre-block: the
// target page may start loading for a moment before we redirect the tab away once the verdict
// comes back. That's an honest limitation, not a bug -- treat this as "catches it within a
// couple seconds", not "never touches the page".
// ---------------------------------------------------------------------------------------------

const inFlight = new Set(); // domains currently being checked, so rapid navigation doesn't double-fire

function registrableDomain(urlString) {
  try {
    const host = new URL(urlString).hostname;
    const parts = host.split(".");
    return parts.length <= 2 ? host : parts.slice(-2).join("."); // good enough for the common case;
    // the backend's own tldextract-based resolution is authoritative for anything trickier (co.uk etc.)
  } catch {
    return null;
  }
}

chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (details.frameId !== 0) return; // only top-level page loads, not iframes/subresources

  const { autoProtectEnabled } = await chrome.storage.local.get("autoProtectEnabled");
  if (!autoProtectEnabled) return;

  const url = details.url;
  if (!url.startsWith("http://") && !url.startsWith("https://")) return;

  const domain = registrableDomain(url);
  if (!domain || domain === "localhost") return;

  const sessionKey = `cleared:${domain}`;
  const { [sessionKey]: cleared } = await chrome.storage.session.get(sessionKey);
  if (cleared) return; // already investigated (or the user chose to proceed) this session

  if (inFlight.has(domain)) return;
  inFlight.add(domain);

  try {
    const data = await callBackend(url);
    const v = data.verdict;

    if (v.verdict === "likely_phishing") {
      await chrome.storage.session.set({
        [`block:${details.tabId}`]: { url, verdict: v, warnings: data.warnings, domain: data.domain || domain },
      });
      chrome.tabs.update(details.tabId, { url: chrome.runtime.getURL("blocked.html") });
      return;
    }

    if (v.verdict === "suspicious") {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: `PhishTrace: ${domain} looks suspicious`,
        message: v.explanation,
      });
    }

    // legitimate or suspicious-but-not-blocked -- don't re-check this domain again this session
    await chrome.storage.session.set({ [sessionKey]: true });
  } catch (err) {
    // fail open: if the backend's unreachable, don't break normal browsing over it
  } finally {
    inFlight.delete(domain);
  }
});
