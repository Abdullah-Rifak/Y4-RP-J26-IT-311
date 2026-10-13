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

function extractCommentIds(article) {
  for (const a of article.querySelectorAll('a[href*="comment_id="]')) {
    const url = new URL(a.href);
    const reply = url.searchParams.get("reply_comment_id");
    const id = url.searchParams.get("comment_id");
    const numericId = id && /^\d+$/.test(id) ? id : null; // skips base64 author links
    if (reply) return { comment_id: reply, thread_root_id: numericId };
    if (numericId) return { comment_id: numericId, thread_root_id: null };
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

// The post id is in every comment's timestamp link: /<page>/posts/<pfbid...>?comment_id=...
function extractPostId(article) {
  for (const a of article.querySelectorAll('a[href*="/posts/"]')) {
    const m = new URL(a.href).pathname.match(/\/posts\/([^/?]+)/);
    if (m) return m[1];
  }
  return null;
}
// Turns a Facebook profile link into the same handle format as author_handle.
// Returns null for hashtags, external links (l.facebook.com) and non-profile paths.
function handleFromHref(href) {
  try {
    const url = new URL(href);
    if (!/(^|\.)facebook\.com$/.test(url.hostname)) return null;
    if (url.hostname === "l.facebook.com") return null;
    if (url.pathname === "/profile.php") return url.searchParams.get("id");
    const parts = url.pathname.split("/").filter(Boolean);
    return parts.length === 1 ? parts[0] : null; // /hashtag/x has 2 parts, so it's skipped
  } catch {
    return null;
  }
}

function extractMentions(article) {
  const el = article.querySelector(TEXT_SELECTOR);
  if (!el) return [];
  const handles = new Set();
  el.querySelectorAll("a[href]").forEach((a) => {
    const h = handleFromHref(a.href);
    if (h) handles.add(h);
  });
  return [...handles];
}
function captureComments() {
  const byId = new Map();
  document
    .querySelectorAll('div[role="article"][aria-label]')
    .forEach((article) => {
      const meta = parseLabel(article.getAttribute("aria-label"));
      if (!meta) return;
      const ids = extractCommentIds(article);
      if (!ids) {
        console.warn("[SNA] no comment_id found for", meta.author);
        return;
      }
      const { comment_id, thread_root_id } = ids;
      if (byId.has(comment_id)) return; // Facebook renders two copies of the thread
      byId.set(comment_id, {
        comment_id,
        post_id: extractPostId(article),
        type: meta.type,
        thread_root_id,
        author: meta.author,
        author_handle: extractAuthorHandle(article),
        reply_to: meta.replyTo,
        text: extractText(article),
        media: extractMedia(article),
        mentions: extractMentions(article),
      });
    });
  return [...byId.values()];
}

// The post's own image(s). Link-preview images carry data-ad-rendering-role="image".
// Facebook renders the post twice, so images are de-duplicated by their original URL.
function capturePost(rows) {
  const media = [];
  const seen = new Set();
  document
    .querySelectorAll('[data-ad-rendering-role="image"]')
    .forEach((el) => {
      extractMedia(el).forEach((m) => {
        if (seen.has(m.url)) return;
        seen.add(m.url);
        media.push(m);
      });
    });
  const fromRows = rows.find((r) => r.post_id);
  const fromUrl = location.pathname.match(/\/posts\/([^/?]+)/);
  return {
    post_id: fromRows ? fromRows.post_id : fromUrl ? fromUrl[1] : null,
    media,
  };
}

// Alt+Shift+C runs a capture. A shortcut is needed because content scripts run in an
// isolated world, so window functions aren't callable from the DevTools console.
document.addEventListener("keydown", (e) => {
  if (e.altKey && e.shiftKey && e.code === "KeyC") {
    const rows = captureComments();
    const post = capturePost(rows);
    console.log(
      `[SNA] post ${post.post_id}: ${post.media.length} image(s)`,
      post.media,
    );
    console.log(`[SNA] captured ${rows.length} comments`);
    console.table(
      rows.map(({ post_id, ...r }) => ({
        ...r,
        mentions: r.mentions.join(", ") || null,
        media: r.media.map((m) => `${m.kind}: ${m.url}`).join(" | ") || null,
      })),
    );
  }
});

console.log("[SNA] content script loaded. Press Alt+Shift+C to capture.");
