import { useCallback, useEffect, useState } from "react";
import * as api from "./api.js";
import { tierLabel } from "./lib.js";
import Detail from "./components/Detail.jsx";
import LoadData from "./components/LoadData.jsx";
import UserList from "./components/UserList.jsx";

const DEFAULT_TIERS = ["none", "warning", "flag", "high_severity_report"];

export default function App() {
  const [tiers, setTiers] = useState(DEFAULT_TIERS);
  const [minTier, setMinTier] = useState("warning");
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [apiOk, setApiOk] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const health = await api.getHealth();
      setTiers(health.tiers);
      setApiOk(true);
      setUsers(await api.getUsers(minTier));
    } catch (e) {
      setApiOk(false);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [minTier]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Moderation review</h1>
          <p className="muted">Recommendations only. A person makes every final decision.</p>
        </div>
        <p className={apiOk === false ? "api-status bad" : "api-status"} role="status">
          {apiOk === null ? "Connecting to the API…" : apiOk ? "API connected" : "API not reachable"}
        </p>
      </header>

      <main className="layout">
        <aside className="sidebar" aria-label="Users and data">
          <LoadData onLoaded={refresh} />

          <div className="filter">
            <label htmlFor="min-tier">Show</label>
            <select id="min-tier" value={minTier} onChange={(e) => setMinTier(e.target.value)}>
              {tiers.map((t) => (
                <option key={t} value={t}>
                  {t === "none" ? "All users" : `${tierLabel(t)} and above`}
                </option>
              ))}
            </select>
            <button type="button" onClick={refresh}>
              Refresh
            </button>
          </div>

          <p role="alert" className="error">
            {error}
          </p>

          <UserList users={users} selectedId={selected} onSelect={setSelected} loading={loading} />
        </aside>

        <section className="detail" aria-label="Selected user">
          {selected ? (
            <Detail key={selected} userId={selected} tiers={tiers} onDecided={refresh} />
          ) : (
            <p className="muted">Select a user to see why they were flagged.</p>
          )}
        </section>
      </main>
    </div>
  );
}
