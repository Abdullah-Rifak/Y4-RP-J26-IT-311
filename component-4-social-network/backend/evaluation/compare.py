"""Run baselines A and B and the proposed score on the same data and show where they differ.

Usage (from the backend folder):
  python -m evaluation.compare                       # the two synthetic posts
  python -m evaluation.compare --post thread.json classifier.json --post t2.json c2.json

IMPORTANT: this shows HOW the methods disagree, not WHICH is right. Deciding that needs
expert-labelled data (proposal section 3.5). On synthetic data it demonstrates the harness only.
"""
import argparse
import json
from pathlib import Path

from escalation.tiers import recommended_tier
from evaluation.baselines import detection_only, proposed, volume_based
from evaluation.metrics import ranking, spearman, top_k_overlap

DATA = Path(__file__).resolve().parent.parent / "data"


def load_posts(pairs):
    return [(json.load(open(t, encoding="utf-8")), json.load(open(c, encoding="utf-8"))) for t, c in pairs]


def show(title, a_scores, b_scores, p_scores):
    users = sorted(set(a_scores) | set(b_scores) | set(p_scores), key=lambda u: (-p_scores.get(u, 0), u))
    print(f"\n{title}")
    print(f"{'user':<12}{'A max sev':>10}{'B count':>9}{'B tier':>22}{'proposed':>10}{'proposed tier':>22}")
    for u in users:
        a, b, p = a_scores.get(u), b_scores.get(u, 0), p_scores.get(u, 0)
        print(f"{u:<12}{'-' if a is None else a:>10}{b:>9}{recommended_tier(b):>22}{p:>10}{recommended_tier(p):>22}")
    rho = spearman(b_scores, p_scores)
    print(f"\n  Spearman, volume (B) vs proposed : {'undefined' if rho is None else f'{rho:.2f}'}")
    print(f"  Top-1 user    A={ranking(a_scores)[:1]}  B={ranking(b_scores)[:1]}  proposed={ranking(p_scores)[:1]}")
    k = min(3, len(users))
    print(f"  Top-{k} overlap, B vs proposed    : {top_k_overlap(b_scores, p_scores, k):.2f}")
    print("  (B's tiers use the same thresholds as the proposed score, applied to the count.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", nargs=2, action="append", metavar=("THREAD", "CLASSIFIER"))
    pairs = ap.parse_args().post or [
        (DATA / "synthetic_thread.json", DATA / "synthetic_classifier.json"),
        (DATA / "synthetic_thread_2.json", DATA / "synthetic_classifier_2.json"),
    ]
    posts = load_posts(pairs)

    first = posts[:1]
    show(f"One post ({first[0][0]['post_id']}): detection only vs volume vs proposed",
         detection_only(*first[0]), volume_based(first), proposed(first))
    if len(posts) > 1:
        show(f"All {len(posts)} posts (history accumulates)",
             {}, volume_based(posts), proposed(posts))
