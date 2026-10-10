const TIME_SUFFIX =
  /\s+(?:(?:about|over|almost|less than)\s+)?(?:\d+|an?|a few|one)\s+(?:second|minute|hour|day|week|month|year)s?\s+ago$|\s+(?:just now|now)$/i;

function parseLabel(label) {
  const clean = label.replace(TIME_SUFFIX, "").trim();
  let m = clean.match(/^Comment by (.+)$/);
  if (m) return { type: "comment", author: m[1], replyTo: null };
  m = clean.match(/^Reply by (.+?) to (.+?)['’]s (?:comment|reply)\b/);
  if (m) return { type: "reply", author: m[1], replyTo: m[2] };
  return null; // the post itself and other articles
}

function extractCommentId(article) {
  for (const a of article.querySelectorAll('a[href*="comment_id="]')) {
    const url = new URL(a.href);
    const reply = url.searchParams.get("reply_comment_id");
    if (reply) return reply;
    const id = url.searchParams.get("comment_id");
    if (id && /^\d+$/.test(id)) return id; // skips the base64 author links
  }
  return null;
}

function extractAuthorHandle(article) {
  const a = article.querySelector('a[role="link"]');
  if (!a) return null;
  const url = new URL(a.href);
  return url.pathname === "/profile.php"
    ? url.searchParams.get("id")
    : url.pathname.split("/")[1] || null;
}

const TEXT_SELECTOR = 'div[dir="auto"][style*="text-align"]';

function extractText(article) {
  const el = article.querySelector(TEXT_SELECTOR);
  if (!el) return null; // image/GIF/sticker-only comment
  const clone = el.cloneNode(true);
  clone.querySelectorAll("img[alt]").forEach((img) => img.replaceWith(img.alt)); // emoji
  return clone.textContent.trim();
}

// Facebook proxies external media (e.g. GIPHY) through fbcdn and keeps the real,
// permanent source in ?url=. Real photos have no ?url=, so their signed fbcdn URL is kept.
function unwrapUrl(src) {
  try {
    return new URL(src).searchParams.get("url") || src;
  } catch {
    return src;
  }
}

function extractMedia(article) {
  const textEl = article.querySelector(TEXT_SELECTOR);
  const gifLabelled = !!article.querySelector('[aria-label*="GIF"]');
  const media = [];
  article.querySelectorAll("img").forEach((img) => {
    const src = img.getAttribute("src") || "";
    if (!src || src.startsWith("data:")) return; // reaction icons
    if (src.includes("emoji.php")) return; // emoji
    if (img.getAttribute("role") === "presentation") return;
    if (textEl && textEl.contains(img)) return; // emoji inside the comment text
    const url = unwrapUrl(src);
    // Photos sit inside a link to photo.php?fbid=<id>; that id is stable, the src is not.
    const link = img.closest("a[href]");
    let photo_id = null;
    if (link) {
      try {
        photo_id = new URL(link.href).searchParams.get("fbid");
      } catch {}
    }
    media.push({
      kind: gifLabelled || /\.gif(\?|$)/i.test(url) ? "gif" : "image",
      url,
      alt: img.alt || null,
      photo_id,
    });
  });
  return media;
}

function captureComments() {
  const byId = new Map();
  document
    .querySelectorAll('div[role="article"][aria-label]')
    .forEach((article) => {
      const meta = parseLabel(article.getAttribute("aria-label"));
      if (!meta) return;
      const comment_id = extractCommentId(article);
      if (!comment_id) {
        console.warn("[SNA] no comment_id found for", meta.author);
        return;
      }
      if (byId.has(comment_id)) return; // Facebook renders two copies of the thread
      byId.set(comment_id, {
        comment_id,
        type: meta.type,
        author: meta.author,
        author_handle: extractAuthorHandle(article),
        reply_to: meta.replyTo,
        text: extractText(article),
        media: extractMedia(article),
      });
    });
  return [...byId.values()];
}

// Alt+Shift+C runs a capture. A shortcut is needed because content scripts run in an
// isolated world, so window functions aren't callable from the DevTools console.
document.addEventListener("keydown", (e) => {
  if (e.altKey && e.shiftKey && e.code === "KeyC") {
    const rows = captureComments();
    console.log(`[SNA] captured ${rows.length} comments`);
    console.table(
      rows.map((r) => ({
        ...r,
        media: r.media.map((m) => `${m.kind}: ${m.url}`).join(" | ") || null,
      })),
    );
  }
});

console.log("[SNA] content script loaded. Press Alt+Shift+C to capture.");
