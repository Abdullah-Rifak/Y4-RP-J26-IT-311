"""All the logic behind the moderation API, in plain Python (no web framework).

Keeps the risk store and ties the pipeline to the escalation rules in escalation/.
app.py only wraps these functions in HTTP routes.
"""
import json
import threading
from pathlib import Path

from escalation.review import append_decision, decisions_for, make_decision, review_status
from escalation.tiers import TIERS, recommended_tier
from justification.justify import build_justification, render_text, verify
from risk_scoring.risk import thread_contributions, update_store, user_risk
from risk_scoring.severity import attach

ROOT = Path(__file__).resolve().parent.parent  # the backend folder
DATA_DIR = ROOT / "data" / "captures"
STORE_PATH = DATA_DIR / "risk_store.json"

_lock = threading.Lock()


class NotFound(Exception):
    pass


# ---- store ----
def load_store() -> dict:
    if STORE_PATH.exists():
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    return {"users": {}}


def save_store(store: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")


def ingest(capture: dict, records: list[dict]) -> dict:
    """Same pipeline as the command line: join severity, score the thread, update the store."""
    try:
        post_id = capture["post_id"]
        scored = attach(capture, records)
        contribs = thread_contributions(capture, scored)
    except KeyError as e:
        raise ValueError(f"malformed capture or record, missing field {e}") from e
    with _lock:
        store = load_store()
        update_store(store, post_id, contribs)
        save_store(store)
    return {
        "post_id": post_id,
        "comments": len(capture["comments"]),
        "unclassified": sum(1 for s in scored if s["severity"] is None),
        "users_flagged": len(contribs),
        "centrality_applied": any(c["centrality_applied"] for c in contribs.values()) if contribs else None,
    }


# ---- reading ----
def list_users(min_tier: str = "warning") -> list[dict]:
    if min_tier not in TIERS:
        raise ValueError(f"min_tier must be one of {TIERS}")
    store = load_store()
    rows = []
    for user in store["users"]:
        risk = user_risk(store, user)
        tier = recommended_tier(risk)
        if TIERS.index(tier) < TIERS.index(min_tier):
            continue
        rows.append({"user": user, "risk": risk, "recommended_tier": tier,
                     "posts": len(store["users"][user]["posts"]), "review_status": review_status(user, risk)})
    rows.sort(key=lambda r: r["risk"], reverse=True)
    return rows


def get_justification(user: str) -> dict:
    store = load_store()
    if user not in store["users"]:
        raise NotFound(f"unknown user {user}")
    j = build_justification(store, user)
    verify(j)  # raises if the explanation and the score ever disagree
    return {**j, "text": render_text(j), "review_status": review_status(user, j["risk"])}


# ---- moderator decisions ----
def record_decision(user: str, decision: str, reviewer: str, note: str = "", final_tier: str | None = None) -> dict:
    store = load_store()
    if user not in store["users"]:
        raise NotFound(f"unknown user {user}")
    entry = make_decision(user, user_risk(store, user), decision, reviewer, note, final_tier)
    append_decision(entry)
    return entry
