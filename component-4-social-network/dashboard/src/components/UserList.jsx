import { shortId, statusLabel, tierLabel } from "../lib.js";

export default function UserList({ users, selectedId, onSelect, loading }) {
  if (!loading && users.length === 0) {
    return <p className="muted">No users at this tier yet. Load a capture to begin.</p>;
  }
  return (
    <ul className="user-list" aria-label="Users ranked by risk">
      {users.map((u) => (
        <li key={u.user}>
          <button
            type="button"
            className="user-row"
            aria-pressed={u.user === selectedId}
            title={u.user}
            onClick={() => onSelect(u.user)}
          >
            <span className="user-id">{shortId(u.user)}</span>
            <span className="user-risk">Risk {u.risk}</span>
            <span className={`badge tier-${u.recommended_tier}`}>{tierLabel(u.recommended_tier)}</span>
            <span className={`badge status-${u.review_status}`}>{statusLabel(u.review_status)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
