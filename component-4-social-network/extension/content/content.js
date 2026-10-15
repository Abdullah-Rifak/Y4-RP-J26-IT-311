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
  clone.querySelectorAll("a[href]").forEach((a) => {
    if (handleFromHref(a.href)) a.replaceWith("@USER");
  });
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
// ---- anonymisation ----
async function getSalt() {
  const { sna_salt } = await chrome.storage.local.get("sna_salt");
  if (sna_salt) return sna_salt;
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  const salt = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  await chrome.storage.local.set({ sna_salt: salt });
  return salt;
}

async function pseudonym(salt, value) {
  if (!value) return null;
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(salt + ":" + value),
  );
  const hex = [...new Uint8Array(buf)]
    .slice(0, 8)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return "u_" + hex;
}

// A reply only knows its target by display name. Resolve it to a handle by looking
// only inside the same thread, so two people with the same name elsewhere can't clash.
function resolveReplyTarget(row, rows) {
  if (row.type !== "reply" || !row.thread_root_id)
    return { handle: null, ambiguous: false };
  const handles = new Set();
  for (const r of rows) {
    const inThread =
      r.comment_id === row.thread_root_id ||
      r.thread_root_id === row.thread_root_id;
    if (
      inThread &&
      r.comment_id !== row.comment_id &&
      r.author === row.reply_to
    )
      handles.add(r.author_handle);
  }
  if (handles.size === 1) return { handle: [...handles][0], ambiguous: false };
  return { handle: null, ambiguous: handles.size > 1 }; // 0 = target not captured (e.g. collapsed)
}
// ---- expansion ----
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// "View 3 more replies", "View 1 reply", "View more comments", "View previous comments",
// plus "See more" but only inside a comment (not the post text).
function findExpanders() {
  const found = [];
  document
    .querySelectorAll('div[role="button"], span[role="button"]')
    .forEach((el) => {
      const label = (el.textContent || "").trim();
      if (!label || label.length > 60) return;
      if (
        /^view (?:all )?\d*\s*(?:more |previous )?(?:repl(?:y|ies)|comments?)/i.test(
          label,
        )
      ) {
        found.push({ el, label });
      } else if (/^see more$/i.test(label)) {
        const art = el.closest('div[role="article"][aria-label]');
        if (art && parseLabel(art.getAttribute("aria-label")))
          found.push({ el, label });
      }
    });
  return found;
}

let expanding = false;
async function expandAll({ maxRounds = 15, delayMs = 1200 } = {}) {
  if (expanding) return;
  expanding = true;
  const clicked = new WeakSet(); // never click the same button twice
  let total = 0;
  for (let round = 1; round <= maxRounds; round++) {
    const targets = findExpanders().filter(({ el }) => !clicked.has(el));
    if (!targets.length) break;
    console.log(
      `[SNA] expand round ${round}: ${targets.length} button(s)`,
      targets.map((t) => t.label),
    );
    for (const { el } of targets) {
      clicked.add(el);
      el.click();
      total++;
      await sleep(300 + Math.random() * 400);
    }
    await sleep(delayMs); // let Facebook load the new replies
  }
  const rows = captureComments();
  const users = new Set(rows.map((r) => r.author_handle)).size;
  console.log(
    `[SNA] expansion done: clicked ${total}; ${rows.length} comments, ${users} unique users (target: 15+ comments, 5+ users)`,
  );
  expanding = false;
}

document.addEventListener("keydown", (e) => {
  if (e.altKey && e.shiftKey && e.code === "KeyE") expandAll();
});
async function anonymise(rows) {
  const salt = await getSalt();
  const out = [];
  for (const r of rows) {
    const target = resolveReplyTarget(r, rows);
    out.push({
      comment_id: r.comment_id,
      post_id: r.post_id,
      type: r.type,
      thread_root_id: r.thread_root_id,
      author_id: await pseudonym(salt, r.author_handle),
      reply_to_id: await pseudonym(salt, target.handle),
      reply_to_ambiguous: target.ambiguous,
      mentions: await Promise.all(r.mentions.map((h) => pseudonym(salt, h))),
      text: r.text,
      media: r.media,
    });
  }
  return out;
}

document.addEventListener("keydown", async (e) => {
  if (e.altKey && e.shiftKey && e.code === "KeyJ") {
    const rows = captureComments();
    const post = capturePost(rows);
    const comments = await anonymise(rows);
    const json = JSON.stringify(
      {
        post_id: post.post_id,
        captured_at: new Date().toISOString(),
        post_media: post.media,
        comments,
      },
      null,
      2,
    );
    try {
      await navigator.clipboard.writeText(json);
      console.log(
        `[SNA] copied anonymised JSON (${comments.length} comments) to clipboard`,
      );
    } catch (err) {
      console.warn("[SNA] clipboard blocked, printing instead", err);
      console.log(json);
    }
  }
});

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

console.log("[SNA] loaded. Alt+Shift+E expand, Alt+Shift+C inspect, Alt+Shift+J copy JSON.");