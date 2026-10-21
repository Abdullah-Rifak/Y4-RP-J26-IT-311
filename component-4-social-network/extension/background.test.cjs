// Run with:  node --test     (from the extension folder)
const test = require("node:test");
const assert = require("node:assert/strict");

const MY_ID = "my-extension-id";
let listener;
let calls;
let nextFetch;

globalThis.chrome = { runtime: { id: MY_ID, onMessage: { addListener: (fn) => { listener = fn; } } } };
globalThis.fetch = async (url, opts) => { calls.push({ url, opts }); return nextFetch(); };
require("./background.js");

const good = { post_id: "pfbid123", comments: [{ comment_id: "1" }] };

// Calls the listener the way Chrome does and resolves with whatever it answers.
function send(msg, sender = { id: MY_ID }) {
  return new Promise((resolve) => {
    const keepOpen = listener(msg, sender, resolve);
    if (keepOpen === false) setTimeout(() => resolve("NO-ANSWER"), 20);
  });
}

test.beforeEach(() => { calls = []; nextFetch = async () => ({ ok: true, status: 200, json: async () => ({ comments: 1 }) }); });

test("a good capture is posted to the local API and the answer is relayed", async () => {
  const res = await send({ type: "sna-capture", payload: good });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://127.0.0.1:8000/capture");
  assert.equal(calls[0].opts.method, "POST");
  assert.equal(calls[0].opts.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(calls[0].opts.body), good);
  assert.deepEqual(res, { ok: true, status: 200, body: { comments: 1 } });
});

test("the listener says it will answer later (returns true) only when it sends a request", () => {
  assert.equal(listener({ type: "sna-capture", payload: good }, { id: MY_ID }, () => {}), true);
  assert.equal(listener({ type: "other" }, { id: MY_ID }, () => {}), false);
});

test("other message types are ignored", async () => {
  assert.equal(await send({ type: "something-else", payload: good }), "NO-ANSWER");
  assert.equal(calls.length, 0);
});

test("messages from another extension are ignored", async () => {
  assert.equal(await send({ type: "sna-capture", payload: good }, { id: "someone-else" }), "NO-ANSWER");
  assert.equal(calls.length, 0);
});

test("a capture with no post id is refused with a helpful message and nothing is sent", async () => {
  for (const bad of [{ post_id: null, comments: [] }, { post_id: "", comments: [] }, { comments: [] }]) {
    const res = await send({ type: "sna-capture", payload: bad });
    assert.equal(res.ok, false);
    assert.match(res.error, /own page/);
  }
  assert.equal(calls.length, 0);
});

test("a malformed capture is refused and nothing is sent", async () => {
  for (const bad of [null, "text", { post_id: "x" }, { post_id: "x", comments: "no" }]) {
    const res = await send({ type: "sna-capture", payload: bad });
    assert.deepEqual(res, { ok: false, error: "malformed capture" });
  }
  assert.equal(calls.length, 0);
});

test("an HTTP error from the API is relayed with its details", async () => {
  nextFetch = async () => ({ ok: false, status: 400, json: async () => ({ detail: "comment 3 is missing ['type']" }) });
  const res = await send({ type: "sna-capture", payload: good });
  assert.deepEqual(res, { ok: false, status: 400, body: { detail: "comment 3 is missing ['type']" } });
});

test("a non-JSON error page does not crash the worker", async () => {
  nextFetch = async () => ({ ok: false, status: 502, json: async () => { throw new Error("not json"); } });
  const res = await send({ type: "sna-capture", payload: good });
  assert.deepEqual(res, { ok: false, status: 502, body: null });
});

test("the API being down gives a message that names the address", async () => {
  nextFetch = async () => { throw new TypeError("Failed to fetch"); };
  const res = await send({ type: "sna-capture", payload: good });
  assert.equal(res.ok, false);
  assert.match(res.error, /Can't reach the API at http:\/\/127\.0\.0\.1:8000/);
});
