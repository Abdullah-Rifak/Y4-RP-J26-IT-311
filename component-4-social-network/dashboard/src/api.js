// Talks to the FastAPI backend. Change the address with VITE_API_URL in a .env file.
const BASE = import.meta.env?.VITE_API_URL ?? "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const init = { ...options };
  if (options.body) init.headers = { "Content-Type": "application/json" };

  let res;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    throw new Error(`Can't reach the API at ${BASE}. Is uvicorn running?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const getHealth = () => request("/health");
export const getUsers = (minTier) => request(`/users?min_tier=${encodeURIComponent(minTier)}`);
export const getJustification = (id) => request(`/users/${encodeURIComponent(id)}/justification`);
export const getDecisions = (id) => request(`/users/${encodeURIComponent(id)}/decisions`);
export const postDecision = (id, body) =>
  request(`/users/${encodeURIComponent(id)}/decisions`, { method: "POST", body: JSON.stringify(body) });
export const ingest = (capture, classifier) =>
  request("/ingest", { method: "POST", body: JSON.stringify({ capture, classifier }) });
