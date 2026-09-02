document.addEventListener("DOMContentLoaded", () => {
  const inputEl = document.getElementById("input");
  const submitEl = document.getElementById("submit");
  const statusEl = document.getElementById("status");
  const stepsEl = document.getElementById("steps");
  const verdictEl = document.getElementById("verdict");

  wireUpForm({ inputEl, submitEl, statusEl, stepsEl, verdictEl });

  // if the user right-clicked "Investigate this link" from the context menu, background.js
  // stashes the link here so opening the popup right after shows the same investigation
  chrome.storage.local.get("prefillInput", ({ prefillInput }) => {
    if (!prefillInput) return;
    inputEl.value = prefillInput;
    chrome.storage.local.remove("prefillInput");
    submitEl.click();
  });
});
