"""Build the reviewer study (proposal sections 3.3 and 3.5, objective 5): do reviewers find the
accumulated, auditable justification clearer and more trustworthy than a per-post explanation
(baseline C) or no explanation?

Design: each reviewer rates several cases, seeing each case in ONE of three conditions, rotated
(Latin square) so every case appears in every condition equally often. The recommended action
is identical in all three; only the explanation differs.
  none      the action alone
  per_post  an explanation of the user's latest post only, no history (baseline C)
  full      the proposed justification: accumulated risk, influence and evidence
This is a within-subject design: it needs far fewer reviewers than comparing separate groups.
Your proposal says 'two groups', so agree this change with your supervisor.

Usage (from the backend folder):
  python -m evaluation.study --scenarios data/eval/tier_scenarios.json --reviewers 9 --cases 6 --out data/eval/study
Gives reviewers their booklet (R01.txt ...) and the blank responses.csv. KEEP assignments.json:
it says which condition each reviewer saw and must not be shared with them.
"""
import argparse
import csv
import json
import random
from pathlib import Path

from escalation.tiers import TIERS, recommended_tier
from justification.justify import build_justification, render_text
from risk_scoring.risk import thread_contributions, update_store, user_risk
from risk_scoring.severity import attach

CONDITIONS = ["none", "per_post", "full"]
CLARITY = "How clear is the reason for this recommendation?  (1 = very unclear, 2 = unclear, 3 = neither, 4 = clear, 5 = very clear)"
TRUST = "How much do you trust this recommendation?  (1 = not at all, 2 = a little, 3 = somewhat, 4 = mostly, 5 = completely)"
EVIDENCE_SHOWN = 3  # comments listed, the same in per_post and full


def _label(tier: str) -> str:
    return "NO ACTION" if tier == "none" else tier.replace("_", " ").upper()


def scenario_store(posts) -> dict:
    store: dict = {"users": {}}
    for capture, records in posts:
        update_store(store, capture["post_id"], thread_contributions(capture, attach(capture, records)))
    return store


def candidate_cases(doc: dict, base: Path) -> list[dict]:
    """Every (scenario, user) that has at least one flagged comment."""
    out = []
    for sc in doc["scenarios"]:
        posts = [(json.loads(Path(base / p["capture"]).read_text(encoding="utf-8")),
                  json.loads(Path(base / p["classifier"]).read_text(encoding="utf-8"))) for p in sc["posts"]]
        store = scenario_store(posts)
        for user in store["users"]:
            out.append({"scenario": sc["id"], "user": user, "store": store,
                        "tier": recommended_tier(user_risk(store, user))})
    return out


def select_cases(cands: list[dict], n: int, seed: int) -> list[dict]:
    """Up to n cases, spread across recommended tiers (round robin), reproducible from the seed."""
    rng = random.Random(seed)
    groups = {t: [c for c in cands if c["tier"] == t] for t in TIERS}
    for g in groups.values():
        rng.shuffle(g)
    chosen = []
    while len(chosen) < min(n, len(cands)):
        for t in TIERS:
            if groups[t] and len(chosen) < n:
                chosen.append(groups[t].pop())
    return chosen


def explanation(case: dict, condition: str) -> str:
    store, user = case["store"], case["user"]
    head = f"Recommended action: {_label(case['tier'])}"
    if condition == "none":
        return head + "\n(No explanation is shown for this recommendation.)"
    if condition == "per_post":
        post_id, p = list(store["users"][user]["posts"].items())[-1]  # the latest post only
        lines = [f"In post {post_id}, {p['flagged']} comment(s) from this user were flagged as hate:"]
        lines += [f"  - comment {e['comment_id']}: {e['category']} (confidence {e['confidence']})"
                  for e in p.get("evidence", [])[:EVIDENCE_SHOWN]]
        return head + "\n" + "\n".join(lines)
    j = build_justification(store, user)
    return head + "\n" + render_text(j).replace(f"User {user}", "This user")


def assign(n_reviewers: int, n_cases: int) -> list[list[str]]:
    """Latin-square rotation: reviewer r sees case i in condition (i + r) mod 3."""
    return [[CONDITIONS[(i + r) % len(CONDITIONS)] for i in range(n_cases)] for r in range(n_reviewers)]


def render_booklet(rid: str, order: list[int], conds: list[str], cases: list[dict], n_total: int) -> str:
    out = [f"REVIEWER BOOKLET {rid}", "",
           "You will read automated moderation recommendations for users of a social media thread and rate them.",
           "Taking part is voluntary and anonymous. You may stop at any time. No personal data is collected.",
           "Ethics clearance reference: [FILL IN BEFORE USE]", "",
           "Give each rating from 1 to 5 using the scale printed under each case.",
           "There are no right or wrong answers; we are testing the explanations, not you.", ""]
    for pos, i in enumerate(order, 1):
        out += ["-" * 70, f"CASE {pos} of {n_total}  (case code C{i + 1:02d})", "",
                explanation(cases[i], conds[i]), "",
                CLARITY, "Your rating: ____", "", TRUST, "Your rating: ____", ""]
    return "\n".join(out)


def build_study(doc: dict, base: Path, out_dir: Path, reviewers: int, n_cases: int, seed: int) -> dict:
    cases = select_cases(candidate_cases(doc, base), n_cases, seed)
    plan = assign(reviewers, len(cases))
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, assignments = [], {}
    for r in range(reviewers):
        rid = f"R{r + 1:02d}"
        order = list(range(len(cases)))
        random.Random(seed * 1000 + r).shuffle(order)  # each reviewer sees the cases in their own order
        (out_dir / f"{rid}.txt").write_text(render_booklet(rid, order, plan[r], cases, len(cases)), encoding="utf-8")
        assignments[rid] = {f"C{i + 1:02d}": plan[r][i] for i in range(len(cases))}
        rows += [{"reviewer_id": rid, "case_id": f"C{i + 1:02d}", "clarity": "", "trust": ""} for i in order]
    with open(out_dir / "responses.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["reviewer_id", "case_id", "clarity", "trust"])
        w.writeheader()
        w.writerows(rows)
    key = {"seed": seed, "conditions": CONDITIONS,
           "cases": {f"C{i + 1:02d}": {"scenario": c["scenario"], "user": c["user"], "recommended_tier": c["tier"]}
                     for i, c in enumerate(cases)},
           "assignments": assignments}
    (out_dir / "assignments.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    return {"cases": len(cases), "reviewers": reviewers, "balanced": len(cases) % len(CONDITIONS) == 0
            and reviewers % len(CONDITIONS) == 0}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--reviewers", type=int, default=9)
    ap.add_argument("--cases", type=int, default=6)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    path = Path(a.scenarios)
    res = build_study(json.loads(Path(path).read_text(encoding="utf-8")), path.parent, Path(a.out), a.reviewers, a.cases, a.seed)
    print(f"Built {res['reviewers']} booklets with {res['cases']} cases each in {a.out}")
    if res["cases"] < a.cases:
        print(f"NOTE: only {res['cases']} cases are available, fewer than the {a.cases} requested.")
    if not res["balanced"]:
        print("NOTE: use a number of reviewers and cases that are both multiples of 3, so every case is "
              "seen in every condition equally often.")
    print("Give reviewers only their R##.txt booklet (and responses.csv rows). Keep assignments.json private.")
