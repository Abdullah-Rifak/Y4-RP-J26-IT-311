"""Turn classifier outputs (category + confidence) into per-comment and per-user severity.

Usage (from the backend folder):
  python -m risk_scoring.severity data/synthetic_thread.json data/synthetic_classifier.json
"""
import json
import sys
from collections import defaultdict

from risk_scoring.config import CATEGORY_WEIGHTS, CONFIDENCE_FLOOR, NOT_HATE

REQUIRED = ("comment_id", "source_component", "predicted_category", "confidence_score")


def severity(category: str, confidence: float) -> float:
    """0 for not_hate or below the confidence floor, else confidence x weight."""
    if category == NOT_HATE or confidence < CONFIDENCE_FLOOR:
        return 0.0
    return round(confidence * CATEGORY_WEIGHTS[category], 3)


def validate(records: list[dict]) -> None:
    problems = []
    for i, r in enumerate(records):
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            problems.append(f"record {i}: missing {missing}")
            continue
        if r["predicted_category"] != NOT_HATE and r["predicted_category"] not in CATEGORY_WEIGHTS:
            problems.append(f"record {i}: unknown category {r['predicted_category']!r}")
        if not 0 <= r["confidence_score"] <= 1:
            problems.append(f"record {i}: confidence {r['confidence_score']} not in [0, 1]")
    if problems:
        raise ValueError("bad classifier output:\n  " + "\n  ".join(problems))


def attach(capture: dict, records: list[dict]) -> list[dict]:
    """Join classifier records to captured comments on comment_id.
    A comment with both text and an image can have two records: the highest severity wins.
    A comment with no record stays None. That means unclassified, which is not the same as 0."""
    validate(records)
    best: dict[str, dict] = {}
    for r in records:
        s = severity(r["predicted_category"], r["confidence_score"])
        cur = best.get(r["comment_id"])
        if cur is None or s > cur["severity"]:
            best[r["comment_id"]] = {
                "severity": s,
                "category": r["predicted_category"],
                "confidence": r["confidence_score"],
                "source": r["source_component"],
            }
    out = []
    for c in capture["comments"]:
        hit = best.get(c["comment_id"])
        out.append(
            {"comment_id": c["comment_id"], "author_id": c["author_id"],
             **(hit or {"severity": None, "category": None, "confidence": None, "source": None})}
        )
    return out


def user_summary(scored: list[dict]) -> list[dict]:
    agg = defaultdict(lambda: {"comments": 0, "unclassified": 0, "flagged": 0, "total": 0.0, "max": 0.0})
    for s in scored:
        a = agg[s["author_id"]]
        a["comments"] += 1
        if s["severity"] is None:
            a["unclassified"] += 1
            continue
        if s["severity"] > 0:
            a["flagged"] += 1
        a["total"] = round(a["total"] + s["severity"], 3)
        a["max"] = max(a["max"], s["severity"])
    rows = [{"user": u, **v} for u, v in agg.items()]
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


if __name__ == "__main__":
    cap_path, rec_path = sys.argv[1], sys.argv[2]
    capture = json.load(open(cap_path, encoding="utf-8"))
    records = json.load(open(rec_path, encoding="utf-8"))
    scored = attach(capture, records)

    print(f"{'comment_id':<10} {'user':<10} {'category':<18} {'conf':>5} {'sev':>6}  source")
    for s in scored:
        sev = "-" if s["severity"] is None else s["severity"]
        print(f"{s['comment_id']:<10} {s['author_id']:<10} {str(s['category']):<18} "
              f"{str(s['confidence']):>5} {sev!s:>6}  {s['source']}")

    unclassified = sum(1 for s in scored if s["severity"] is None)
    print(f"\nunclassified comments: {unclassified} of {len(scored)}")
    print(f"\n{'user':<10}{'comments':>9}{'flagged':>9}{'unclass':>9}{'total_sev':>11}{'max_sev':>9}")
    for r in user_summary(scored):
        print(f"{r['user']:<10}{r['comments']:>9}{r['flagged']:>9}{r['unclassified']:>9}{r['total']:>11}{r['max']:>9}")
