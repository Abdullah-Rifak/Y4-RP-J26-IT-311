// Service worker. The Facebook page cannot call the local API itself (cross-origin rules),
// so the content script hands the capture to this worker, which sends it.
// It only accepts messages from this extension, and only forwards to the local API.
const API_BASE = "http://127.0.0.1:8000";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) return false; // ignore anything from another extension
  if (!msg || msg.type !== "sna-capture") return false;

  const p = msg.payload;
  if (!p || typeof p !== "object" || !Array.isArray(p.comments)) {
    sendResponse({ ok: false, error: "malformed capture" });
    return false;
  }
  if (typeof p.post_id !== "string" || !p.post_id) {
    sendResponse({ ok: false, error: "no post id found: open the post on its own page and try again" });
    return false;
  }

  fetch(`${API_BASE}/capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(p),
  })
    .then(async (res) => {
      let body = null;
      try {
        body = await res.json();
      } catch {
        /* the error page may not be JSON */
      }
      sendResponse({ ok: res.ok, status: res.status, body });
    })
    .catch((err) => {
      sendResponse({ ok: false, error: `Can't reach the API at ${API_BASE}: ${err.message}` });
    });
  return true; // the answer comes later
});
