import { useState } from "react";
import * as api from "../api.js";

async function readJson(file, label) {
  try {
    return JSON.parse(await file.text());
  } catch {
    throw new Error(`${label} is not valid JSON.`);
  }
}

export default function LoadData({ onLoaded }) {
  const [capture, setCapture] = useState(null);
  const [classifier, setClassifier] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!capture || !classifier) {
      setError("Choose both files first.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const res = await api.ingest(
        await readJson(capture, "The capture file"),
        await readJson(classifier, "The classifier file"),
      );
      setMessage(
        `Loaded post ${res.post_id}: ${res.comments} comments, ${res.users_flagged} flagged user(s), ${res.unclassified} unclassified.`,
      );
      onLoaded();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="card">
      <summary>Load a capture</summary>
      <form onSubmit={submit} className="stack">
        <label>
          Capture JSON (from Alt+Shift+J)
          <input type="file" accept=".json,application/json" onChange={(e) => setCapture(e.target.files[0] ?? null)} />
        </label>
        <label>
          Classifier output JSON
          <input type="file" accept=".json,application/json" onChange={(e) => setClassifier(e.target.files[0] ?? null)} />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Loading…" : "Load"}
        </button>
        <p role="status" className="ok">
          {message}
        </p>
        <p role="alert" className="error">
          {error}
        </p>
      </form>
    </details>
  );
}
