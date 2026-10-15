"""Stage 6 of 6: plain-language justification for each recommended tier.

Every number in the text comes from the stored risk data, and verify() recomputes the
arithmetic before anything is shown, so the explanation cannot drift from the score.
No generated text: it is a fixed template filled with stored values.

Usage (from the backend folder):
  python -m justification.justify                 # every user at warning or above
  python -m justification.justify --user u_syn_a
  python -m justification.justify --all
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from escalation.tiers import TIER_THRESHOLDS, next_tier, recommended_tier
from risk_scoring.risk import user_risk

ROOT = Path(__file__).resolve().parent.parent  # the backend folder


def build_justification(store: dict, user: str) -> dict:
    risk = user_risk(store, user)
    tier = recommended_tier(risk)
    nxt = next_tier(risk)
    posts = []
    for post_id, p in store["users"][user]["posts"].items():
        cats = Counter(e["category"] for e in p.get("evidence", []))
        posts.append({"post_id": post_id, **p, "categories": dict(cats)})
    posts.sort(key=lambda p: p["contribution"], reverse=True)
    return {
        "user": user, "risk": risk, "tier": tier,
        "threshold": dict(TIER_THRESHOLDS).get(tier),
        "next_tier": nxt[0] if nxt else None, "next_threshold": nxt[1] if nxt else None,
        "posts": posts,
    }


def verify(j: dict) -> None:
    """Recompute the arithmetic from the stored parts. Raises if anything disagrees."""
    total = round(sum(p["contribution"] for p in j["posts"]), 3)
    assert total == j["risk"], f"posts add up to {total}, not {j['risk']}"
    for p in j["posts"]:
        expect = p["total_severity"] * (1 + p["influence"])
        assert abs(expect - p["contribution"]) < 0.002, f"post {p['post_id']}: contribution mismatch"
        if p.get("evidence"):
            ev = sum(e["severity"] for e in p["evidence"])
            assert abs(ev - p["total_severity"]) < 0.002, f"post {p['post_id']}: evidence mismatch"


def influence_label(x: float) -> str:
    return "high" if x >= 0.75 else "moderate" if x >= 0.25 else "low" if x > 0 else "none"


def render_text(j: dict) -> str:
    name = j["tier"].replace("_", " ")
    if j["tier"] == "none":
        head = f"User {j['user']}: no tier reached (risk {j['risk']})."
    else:
        head = f"User {j['user']}: recommended tier {name.upper()} (risk {j['risk']}, {name} threshold {j['threshold']})."
    if j["next_tier"]:
        head += f" Next tier: {j['next_tier'].replace('_', ' ')} at {j['next_threshold']}."
    lines = [head]
    for p in j["posts"]:
        cats = ", ".join(f"{c} x{n}" for c, n in p["categories"].items()) or "details not stored"
        lines.append(f"- Post {p['post_id']}: {p['flagged']} flagged comment(s) ({cats}), total severity {p['total_severity']}.")
        if p["centrality_applied"]:
            lines.append(
                f"    Influence in this thread: {influence_label(p['influence'])} ({p['influence']}, the mean of "
                f"in-degree {p['in_degree_norm']} and betweenness {p['betweenness_norm']}, each relative to the thread's top user)."
            )
        else:
            lines.append("    Thread too small to measure influence, so influence counts as 0.")
        lines.append(f"    Contribution: {p['total_severity']} x (1 + {p['influence']}) = {p['contribution']}.")
        for e in p.get("evidence", [])[:3]:
            lines.append(f"    Evidence: comment {e['comment_id']} - {e['category']}, confidence {e['confidence']}, severity {e['severity']} ({e['source']}).")
    lines.append("This is a recommendation only. A human moderator makes the final decision.")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=str(ROOT / "data" / "captures" / "risk_store.json"))
    ap.add_argument("--user")
    ap.add_argument("--all", action="store_true", help="include users below the warning tier")
    a = ap.parse_args()
    store = json.load(open(a.store, encoding="utf-8"))

    users = [a.user] if a.user else sorted(store["users"], key=lambda u: user_risk(store, u), reverse=True)
    shown = 0
    for u in users:
        j = build_justification(store, u)
        if j["tier"] == "none" and not (a.all or a.user):
            continue
        verify(j)
        print(render_text(j), end="\n\n")
        shown += 1
    if not shown:
        print("No user has reached the warning tier.")
