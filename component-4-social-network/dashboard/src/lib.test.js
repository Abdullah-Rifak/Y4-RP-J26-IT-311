import test from "node:test";
import assert from "node:assert/strict";
import {
  decisionPayload, formatTime, overrideOptions, shortId, statusLabel, tierLabel, validateDecision,
} from "./lib.js";

const TIERS = ["none", "warning", "flag", "high_severity_report"];

test("tierLabel", () => {
  assert.equal(tierLabel("none"), "No action");
  assert.equal(tierLabel("flag"), "Flag");
  assert.equal(tierLabel("high_severity_report"), "High severity report");
});

test("statusLabel", () => {
  assert.equal(statusLabel("pending"), "Needs review");
  assert.equal(statusLabel("changed_since_review"), "Changed since review");
});

test("shortId", () => {
  assert.equal(shortId("u_syn_a"), "u_syn_a");
  assert.equal(shortId("u_71364afa66dc0a64"), "u_7136…0a64");
});

test("overrideOptions removes the recommended tier", () => {
  assert.deepEqual(overrideOptions(TIERS, "flag"), ["none", "warning", "high_severity_report"]);
});

test("validateDecision: accept", () => {
  assert.equal(validateDecision({ mode: "accept", reviewer: "m1", note: "", finalTier: "", recommended: "flag" }), null);
  assert.match(validateDecision({ mode: "accept", reviewer: "  ", note: "", finalTier: "", recommended: "flag" }), /reviewer/);
});

test("validateDecision: override rules match the server", () => {
  const base = { mode: "override", reviewer: "m1", note: "context was fine", finalTier: "none", recommended: "flag" };
  assert.equal(validateDecision(base), null);
  assert.match(validateDecision({ ...base, finalTier: "" }), /Choose the tier/);
  assert.match(validateDecision({ ...base, finalTier: "flag" }), /must differ/);
  assert.match(validateDecision({ ...base, note: "   " }), /reason/);
  assert.match(validateDecision({ ...base, mode: "other" }), /accept or override/);
});

test("decisionPayload", () => {
  assert.deepEqual(
    decisionPayload({ mode: "accept", reviewer: " m1 ", note: " ", finalTier: "flag" }),
    { decision: "accept", reviewer: "m1", note: "" },
  );
  assert.deepEqual(
    decisionPayload({ mode: "override", reviewer: "m1", note: " ok ", finalTier: "none" }),
    { decision: "override", reviewer: "m1", note: "ok", final_tier: "none" },
  );
});

test("formatTime falls back to the raw text", () => {
  assert.equal(formatTime("not a date"), "not a date");
});
