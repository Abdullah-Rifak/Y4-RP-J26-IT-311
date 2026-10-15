import { useState } from "react";
import * as api from "../api.js";
import { decisionPayload, overrideOptions, tierLabel, validateDecision } from "../lib.js";

function loadReviewer() {
  try {
    return localStorage.getItem("sna_reviewer") ?? "";
  } catch {
    return "";
  }
}

export default function DecisionForm({ userId, recommended, tiers, onSaved }) {
  const [reviewer, setReviewer] = useState(loadReviewer);
  const [mode, setMode] = useState("accept");
  const [finalTier, setFinalTier] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  async function submit(e) {
    e.preventDefault();
    const problem = validateDecision({ mode, reviewer, note, finalTier, recommended });
    if (problem) {
      setError(problem);
      setSaved("");
      return;
    }
    setBusy(true);
    setError("");
    setSaved("");
    try {
      await api.postDecision(userId, decisionPayload({ mode, reviewer, note, finalTier }));
      try {
        localStorage.setItem("sna_reviewer", reviewer.trim());
      } catch {
        /* storage unavailable: fine */
      }
      setSaved("Decision recorded.");
      setMode("accept");
      setFinalTier("");
      setNote("");
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card stack">
      <h3>Your decision</h3>

      <label>
        Reviewer (your name or ID)
        <input type="text" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
      </label>

      <fieldset>
        <legend>What do you decide?</legend>
        <label className="inline">
          <input type="radio" name="mode" value="accept" checked={mode === "accept"} onChange={() => setMode("accept")} />
          Accept the recommendation ({tierLabel(recommended)})
        </label>
        <label className="inline">
          <input type="radio" name="mode" value="override" checked={mode === "override"} onChange={() => setMode("override")} />
          Override it
        </label>
      </fieldset>

      {mode === "override" && (
        <>
          <label>
            Record this tier instead
            <select value={finalTier} onChange={(e) => setFinalTier(e.target.value)}>
              <option value="">Choose…</option>
              {overrideOptions(tiers, recommended).map((t) => (
                <option key={t} value={t}>
                  {tierLabel(t)}
                  {t === "none" ? " (dismiss)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Reason (required for an override)
            <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
        </>
      )}

      <button type="submit" disabled={busy}>
        {busy ? "Saving…" : "Record decision"}
      </button>
      <p role="status" className="ok">
        {saved}
      </p>
      <p role="alert" className="error">
        {error}
      </p>
    </form>
  );
}
