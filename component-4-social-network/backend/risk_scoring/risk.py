"""Stage 4 of 6: the persistent per-user risk score.

Per post:   contribution = total severity x (1 + influence)
            influence    = mean of in-degree and betweenness, each divided by the thread maximum
Per user:   risk = sum of contributions over every post seen so far (never decays)

Re-capturing the same post replaces that post's entry, so a thread is never double counted.
Only users with at least one flagged comment are stored.

Usage (from the backend folder):
  python -m risk_scoring.risk data/synthetic_thread.json data/synthetic_classifier.json
"""
import argparse
import json
from pathlib import Path

from centrality.centrality import centrality_table, influence_scores, thread_big_enough
from escalation.tiers import recommended_tier
from graph.build_graph import build_graph
from risk_scoring.severity import attach, user_summary

ROOT = Path(__file__).resolve().parent.parent  # the backend folder


def thread_contributions(capture: dict, scored: list[dict]) -> dict:
    """What this one post adds to each flagged user's risk, with every input kept
    so the justification can quote the exact numbers."""
    applied = thread_big_enough(capture)
    infl = influence_scores(centrality_table(build_graph(capture))) if applied else {}
    evidence = {}
    for sc in scored:
        if sc["severity"]:  # flagged: severity above 0
            evidence.setdefault(sc["author_id"], []).append(
                {"comment_id": sc["comment_id"], "category": sc["category"],
                 "confidence": sc["confidence"], "severity": sc["severity"], "source": sc["source"]}
            )
    out = {}
    for u in user_summary(scored):
        if u["flagged"] == 0:
            continue
        i, b, c = infl.get(u["user"], (0.0, 0.0, 0.0))
        out[u["user"]] = {
            "flagged": u["flagged"],
            "total_severity": u["total"],
            "in_degree_norm": i,
            "betweenness_norm": b,
            "influence": c,
            "centrality_applied": applied,
            "contribution": round(u["total"] * (1 + c), 3),
            "evidence": sorted(evidence.get(u["user"], []), key=lambda e: e["severity"], reverse=True),
        }
    return out


def update_store(store: dict, post_id: str, contributions: dict) -> None:
    # drop this post's old entries first, so re-capturing a thread replaces it
    for rec in store["users"].values():
        rec["posts"].pop(post_id, None)
    for user, c in contributions.items():
        store["users"].setdefault(user, {"posts": {}})["posts"][post_id] = c
    store["users"] = {u: r for u, r in store["users"].items() if r["posts"]}


def user_risk(store: dict, user: str) -> float:
    return round(sum(p["contribution"] for p in store["users"][user]["posts"].values()), 3)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("capture")
    ap.add_argument("classifier")
    ap.add_argument("--store", default=str(ROOT / "data" / "captures" / "risk_store.json"))
    a = ap.parse_args()

    capture = json.load(open(a.capture, encoding="utf-8"))
    records = json.load(open(a.classifier, encoding="utf-8"))
    store_path = Path(a.store)
    store = json.load(open(store_path, encoding="utf-8")) if store_path.exists() else {"users": {}}

    scored = attach(capture, records)
    contribs = thread_contributions(capture, scored)
    update_store(store, capture["post_id"], contribs)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(store, open(store_path, "w", encoding="utf-8"), indent=2)

    print(f"post {capture['post_id']}: centrality "
          f"{'applied' if thread_big_enough(capture) else 'NOT applied (thread below minimum size)'}")
    print(f"\n{'user':<10}{'flagged':>8}{'sum_sev':>9}{'influence':>10}{'this_post':>10}{'risk':>8}  recommended tier")
    for user, c in sorted(contribs.items(), key=lambda kv: user_risk(store, kv[0]), reverse=True):
        r = user_risk(store, user)
        print(f"{user:<10}{c['flagged']:>8}{c['total_severity']:>9}{c['influence']:>10}"
              f"{c['contribution']:>10}{r:>8}  {recommended_tier(r)}")
    print("\nTiers are recommendations only: a human moderator reviews every one.")
