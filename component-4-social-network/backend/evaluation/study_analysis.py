"""Analyse the reviewer study: clarity and trust, full justification vs per-post (baseline C)
and vs no explanation.

Usage (from the backend folder):  python -m evaluation.study_analysis data/eval/study
(the folder holds the filled-in responses.csv and the private assignments.json)

Unit of analysis is the REVIEWER: each reviewer's ratings are averaged within a condition, then
conditions are compared pair by pair with an exact Wilcoxon signed-rank test. Treating every
single rating as independent would overstate the evidence, because one person gave several.
The four tests are Holm-adjusted together.
"""
import csv
import json
import statistics
import sys
from pathlib import Path

from evaluation.stats import holm, min_possible_p, wilcoxon_exact

OUTCOMES = ("clarity", "trust")
COMPARISONS = [("full", "per_post"), ("full", "none")]
CLEAR_AT = 4  # "clear" or "very clear"
NFR_TARGET = 0.8  # at least 80% of reviewers rate the justification clear or very clear


def load_responses(csv_path: Path, key: dict) -> tuple[list[dict], int]:
    rows, blank = [], 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["clarity"].strip() and not r["trust"].strip():
                blank += 1
                continue
            try:
                cond = key["assignments"][r["reviewer_id"]][r["case_id"]]
            except KeyError:
                raise ValueError(f"row {r['reviewer_id']}/{r['case_id']} is not in assignments.json")
            vals = {}
            for o in OUTCOMES:
                try:
                    vals[o] = int(r[o])
                except ValueError:
                    raise ValueError(f"{r['reviewer_id']}/{r['case_id']}: {o} must be a whole number 1-5, got '{r[o]}'")
                if not 1 <= vals[o] <= 5:
                    raise ValueError(f"{r['reviewer_id']}/{r['case_id']}: {o} must be 1-5, got {vals[o]}")
            rows.append({"reviewer": r["reviewer_id"], "case": r["case_id"], "condition": cond, **vals})
    return rows, blank


def reviewer_means(rows: list[dict], outcome: str) -> dict:
    acc: dict = {}
    for r in rows:
        acc.setdefault(r["condition"], {}).setdefault(r["reviewer"], []).append(r[outcome])
    return {c: {rev: statistics.mean(v) for rev, v in d.items()} for c, d in acc.items()}


def analyse(rows: list[dict]) -> dict:
    desc = {}
    for cond in ("none", "per_post", "full"):
        mine = [r for r in rows if r["condition"] == cond]
        desc[cond] = {"ratings": len(mine)}
        for o in OUTCOMES:
            vals = [r[o] for r in mine]
            desc[cond][o] = {"mean": statistics.mean(vals), "median": statistics.median(vals)} if vals else None
        desc[cond]["pct_clear"] = sum(1 for r in mine if r["clarity"] >= CLEAR_AT) / len(mine) if mine else None

    tests = []
    for o in OUTCOMES:
        means = reviewer_means(rows, o)
        for a, b in COMPARISONS:
            both = sorted(set(means.get(a, {})) & set(means.get(b, {})))
            diffs = [means[a][r] - means[b][r] for r in both]
            w = wilcoxon_exact(diffs)
            tests.append({"outcome": o, "a": a, "b": b, "reviewers": len(both), "n_nonzero": w["n"],
                          "median_diff": statistics.median(diffs) if diffs else None, "p": w["p"],
                          "min_p": min_possible_p(w["n"])})
    for t, adj in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = adj

    all_reviewers = {r["reviewer"] for r in rows}
    incomplete = sorted(rev for rev in all_reviewers
                        if {r["condition"] for r in rows if r["reviewer"] == rev} != {"none", "per_post", "full"})
    full = desc["full"]["pct_clear"]
    return {"descriptives": desc, "tests": tests, "reviewers": len(all_reviewers), "incomplete": incomplete,
            "nfr_clear_share": full, "nfr_met": None if full is None else full >= NFR_TARGET}


def warnings_for(res: dict) -> list[str]:
    w = []
    if res["incomplete"]:
        w.append(f"reviewers who did not rate all three conditions are left out of the paired tests: {res['incomplete']}")
    for t in res["tests"]:
        if t["n_nonzero"] and t["min_p"] >= 0.05:
            w.append(f"{t['outcome']}, {t['a']} vs {t['b']}: only {t['n_nonzero']} reviewer(s) differ, so the smallest "
                     f"possible p is {t['min_p']:.3f} and it can never reach 0.05. You need more reviewers.")
    if res["reviewers"] < 8:
        w.append(f"only {res['reviewers']} reviewers: too few for a reliable result")
    return w


def fmt(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    key = json.loads(Path(folder / "assignments.json").read_text(encoding="utf-8"))
    rows, blank = load_responses(folder / "responses.csv", key)
    if not rows:
        print(f"No ratings in responses.csv yet ({blank} blank rows).")
        sys.exit(0)
    res = analyse(rows)
    print(f"{res['reviewers']} reviewers, {len(rows)} ratings ({blank} blank rows skipped)\n")
    print(f"{'condition':<10}{'ratings':>8}{'clarity mean':>14}{'median':>8}{'trust mean':>12}{'median':>8}{'clear/very clear':>18}")
    for cond, d in res["descriptives"].items():
        c, t = d["clarity"], d["trust"]
        print(f"{cond:<10}{d['ratings']:>8}{fmt(c and c['mean']):>14}{fmt(c and c['median'], 1):>8}"
              f"{fmt(t and t['mean']):>12}{fmt(t and t['median'], 1):>8}{fmt(d['pct_clear'] and d['pct_clear'] * 100, 0):>17}%")
    print(f"\n{'outcome':<9}{'comparison':<20}{'reviewers':>10}{'median diff':>13}{'p':>8}{'p (Holm)':>10}")
    for t in res["tests"]:
        print(f"{t['outcome']:<9}{t['a'] + ' - ' + t['b']:<20}{t['reviewers']:>10}{fmt(t['median_diff']):>13}"
              f"{fmt(t['p'], 3):>8}{fmt(t['p_holm'], 3):>10}")
    print(f"\nTarget: {NFR_TARGET:.0%} rate the full justification clear or very clear. "
          f"Observed {fmt(res['nfr_clear_share'] and res['nfr_clear_share'] * 100, 0)}%: "
          f"{'MET' if res['nfr_met'] else 'NOT met'}")
    for w in warnings_for(res):
        print("WARNING:", w)
