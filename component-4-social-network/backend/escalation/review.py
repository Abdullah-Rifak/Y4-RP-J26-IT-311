"""Stage 5 (continued): the human-in-the-loop half of escalation.

tiers.py says what the system RECOMMENDS. This file holds the rules for what a human
moderator may RECORD about that recommendation, and the append-only review log.
Nothing here ever acts on an account: it only keeps the moderator's decision.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from escalation.tiers import TIERS, recommended_tier

ROOT = Path(__file__).resolve().parent.parent  # the backend folder
LOG_PATH = ROOT / "data" / "captures" / "review_log.jsonl"  # one JSON object per line
_lock = threading.Lock()


# ---- the log ----
def read_log(path: Path = LOG_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def decisions_for(user: str, path: Path = LOG_PATH) -> list[dict]:
    return [d for d in read_log(path) if d["user"] == user]


def review_status(user: str, risk: float, path: Path = LOG_PATH) -> str:
    """pending: never reviewed. reviewed: up to date. changed_since_review: risk has
    gone up since the moderator last looked, so it needs another look."""
    ds = decisions_for(user, path)
    if not ds:
        return "pending"
    return "changed_since_review" if risk > ds[-1]["risk"] else "reviewed"


def append_decision(entry: dict, path: Path = LOG_PATH) -> None:
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


# ---- the rules ----
def make_decision(user: str, risk: float, decision: str, reviewer: str,
                  note: str = "", final_tier: str | None = None) -> dict:
    """Validate a moderator's decision against the current recommendation and return the
    log entry. Raises ValueError if the decision isn't allowed. Does no I/O."""
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    recommended = recommended_tier(risk)

    if decision == "accept":
        final = recommended
    elif decision == "override":
        if final_tier not in TIERS:
            raise ValueError(f"final_tier must be one of {TIERS}")
        if final_tier == recommended:
            raise ValueError("override must differ from the recommendation (use accept instead)")
        if not note.strip():
            raise ValueError("an override needs a written reason")
        final = final_tier  # "none" means the moderator dismissed the recommendation
    else:
        raise ValueError("decision must be 'accept' or 'override'")

    return {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "user": user,
            "decision": decision, "recommended_tier": recommended, "risk": risk,
            "final_tier": final, "reviewer": reviewer.strip(), "note": note.strip()}
