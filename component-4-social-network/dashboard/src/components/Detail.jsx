import { useEffect, useState } from "react";
import * as api from "../api.js";
import { formatTime, statusLabel, tierLabel } from "../lib.js";
import DecisionForm from "./DecisionForm.jsx";

export default function Detail({ userId, tiers, onDecided }) {
  const [data, setData] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError("");
    Promise.all([api.getJustification(userId), api.getDecisions(userId)])
      .then(([justification, history]) => {
        if (cancelled) return;
        setData(justification);
        setDecisions(history);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [userId, reloadKey]);

  function handleSaved() {
    setReloadKey((k) => k + 1);
    onDecided();
  }

  if (error) return <p role="alert" className="error">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;

  return (
    <article>
      <h2>User {data.user}</h2>
      <p className="summary">
        <span className={`badge tier-${data.tier}`}>{tierLabel(data.tier)}</span>
        <span>recommended, risk <strong>{data.risk}</strong></span>
        <span className={`badge status-${data.review_status}`}>{statusLabel(data.review_status)}</span>
      </p>

      <h3>Why this recommendation</h3>
      <pre className="justification">{data.text}</pre>

      <h3>Flagged comments by post</h3>
      {data.posts.map((p) => (
        <details key={p.post_id} className="card">
          <summary>
            Post {p.post_id} (adds {p.contribution} to the risk)
          </summary>
          {p.evidence && p.evidence.length > 0 ? (
            <div className="table-wrap">
              <table>
                <caption className="sr-only">Flagged comments in post {p.post_id}</caption>
                <thead>
                  <tr>
                    <th scope="col">Comment</th>
                    <th scope="col">Category</th>
                    <th scope="col">Confidence</th>
                    <th scope="col">Severity</th>
                    <th scope="col">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {p.evidence.map((e) => (
                    <tr key={e.comment_id}>
                      <td>{e.comment_id}</td>
                      <td>{e.category}</td>
                      <td>{e.confidence}</td>
                      <td>{e.severity}</td>
                      <td>{e.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No comment details were stored for this post.</p>
          )}
        </details>
      ))}

      <DecisionForm key={userId} userId={userId} recommended={data.tier} tiers={tiers} onSaved={handleSaved} />

      <h3>Decision history</h3>
      {decisions.length === 0 ? (
        <p className="muted">No decisions recorded yet.</p>
      ) : (
        <ol className="history">
          {[...decisions].reverse().map((d) => (
            <li key={d.ts + d.reviewer} className="card">
              <p>
                <strong>{d.decision === "accept" ? "Accepted" : "Overrode"}</strong> by {d.reviewer} on {formatTime(d.ts)}
              </p>
              <p>
                Recommended {tierLabel(d.recommended_tier)} at risk {d.risk}; recorded {tierLabel(d.final_tier)}.
              </p>
              {d.note && <p>Reason: {d.note}</p>}
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
