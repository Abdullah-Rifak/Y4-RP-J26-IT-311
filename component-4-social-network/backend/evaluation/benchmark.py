"""Latency check for the response-time and scalability targets (proposal section 5.4).

Usage (from the backend folder):  python -m evaluation.benchmark
Builds seeded synthetic threads of growing size and times graph + centrality + risk scoring.
Numbers depend on the machine, so run it on the laptop you will demo on.
"""
import random
import statistics
import time

from centrality.centrality import centrality_table
from graph.build_graph import build_graph
from risk_scoring.risk import thread_contributions
from risk_scoring.severity import attach

CATEGORIES = ["racial_ethnic", "religious", "political", "gender_based", "sexual_orientation"]


def make_thread(n_comments: int, n_users: int, seed: int = 1, hate_share: float = 0.3):
    """A random but reproducible thread: ~40% replies, ~hate_share of comments flagged."""
    rng = random.Random(seed)
    users = [f"u_{i:04d}" for i in range(n_users)]
    comments, records, top_level = [], [], []
    for i in range(n_comments):
        cid, author = str(1000 + i), rng.choice(users)
        if top_level and rng.random() < 0.4:
            root = rng.choice(top_level)
            comments.append(dict(comment_id=cid, post_id="bench", type="reply", thread_root_id=root["comment_id"],
                                 author_id=author, reply_to_id=root["author_id"], reply_to_ambiguous=False,
                                 mentions=[root["author_id"]], text="", media=[]))
        else:
            c = dict(comment_id=cid, post_id="bench", type="comment", thread_root_id=None, author_id=author,
                     reply_to_id=None, reply_to_ambiguous=False, mentions=[], text="", media=[])
            comments.append(c)
            top_level.append(c)
        hate = rng.random() < hate_share
        records.append(dict(comment_id=cid, source_component="bench",
                            predicted_category=rng.choice(CATEGORIES) if hate else "not_hate",
                            confidence_score=round(rng.uniform(0.5, 0.99), 2)))
    return {"post_id": "bench", "comments": comments}, records


def run_once(capture, records):
    scored = attach(capture, records)
    centrality_table(build_graph(capture))
    thread_contributions(capture, scored)


def time_ms(n_comments, n_users, repeats=5):
    capture, records = make_thread(n_comments, n_users)
    run_once(capture, records)  # warm-up
    samples = []
    for _ in range(repeats):
        t = time.perf_counter()
        run_once(capture, records)
        samples.append((time.perf_counter() - t) * 1000)
    return statistics.median(samples)


if __name__ == "__main__":
    print(f"{'comments':>9}{'users':>7}{'median ms':>11}")
    results = {}
    for n_comments, n_users in [(50, 20), (200, 60), (200, 150), (1500, 500), (1500, 600)]:
        results[(n_comments, n_users)] = ms = time_ms(n_comments, n_users)
        print(f"{n_comments:>9}{n_users:>7}{ms:>11.1f}")
    ref = results[(200, 60)]
    print(f"\nTarget: a 200-comment thread in <= 5000 ms. Measured: {ref:.1f} ms "
          f"({'meets' if ref <= 5000 else 'MISSES'} the target).")
    big = results[(1500, 500)]
    print(f"A 500-user thread took {big:.1f} ms, {big / ref:.1f}x the 200-comment case. "
          "The proposal's '20% latency increase' needs a stated reference size to be testable.")
