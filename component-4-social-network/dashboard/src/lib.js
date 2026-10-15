// Plain helpers with no React in them, so they can be tested with `npm test`.

export function tierLabel(tier) {
  if (tier === "none") return "No action";
  return tier.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

export function statusLabel(status) {
  if (status === "pending") return "Needs review";
  if (status === "reviewed") return "Reviewed";
  if (status === "changed_since_review") return "Changed since review";
  return status;
}

// "u_71364afa66dc0a64" -> "u_7136…0a64"; short ids are left alone.
export function shortId(id) {
  return id.length > 14 ? `${id.slice(0, 6)}…${id.slice(-4)}` : id;
}

export function overrideOptions(tiers, recommended) {
  return tiers.filter((t) => t !== recommended);
}

// Mirrors the server's rules (escalation/review.py) so mistakes are caught before sending.
// The server still checks everything again.
export function validateDecision({ mode, reviewer, note, finalTier, recommended }) {
  if (!reviewer.trim()) return "Enter your name or ID as the reviewer.";
  if (mode === "accept") return null;
  if (mode !== "override") return "Choose accept or override.";
  if (!finalTier) return "Choose the tier you want to record instead.";
  if (finalTier === recommended) return "An override must differ from the recommendation. Use accept instead.";
  if (!note.trim()) return "Write a short reason for the override.";
  return null;
}

export function decisionPayload({ mode, reviewer, note, finalTier }) {
  const body = { decision: mode, reviewer: reviewer.trim(), note: note.trim() };
  if (mode === "override") body.final_tier = finalTier;
  return body;
}

export function formatTime(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}
