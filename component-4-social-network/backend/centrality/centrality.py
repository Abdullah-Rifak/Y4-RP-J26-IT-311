"""Stage 3 of 6: degree and betweenness centrality, and the influence score built from them.

Usage (from the backend folder):  python -m centrality.centrality data/sample_thread.json
"""
import json
import sys

import networkx as nx

from graph.build_graph import POST, build_graph

# Centrality is only meaningful on a thread of reasonable size (proposal section 3.2).
MIN_COMMENTS = 15
MIN_USERS = 6  # "more than 5 users"


def thread_big_enough(capture: dict) -> bool:
    users = {c["author_id"] for c in capture["comments"] if c["author_id"]}
    return len(capture["comments"]) >= MIN_COMMENTS and len(users) >= MIN_USERS


def thread_checks(capture: dict) -> list[str]:
    """Human-readable reasons a thread is below the proposal's minimum size."""
    users = {c["author_id"] for c in capture["comments"] if c["author_id"]}
    msgs = []
    if len(capture["comments"]) < MIN_COMMENTS:
        msgs.append(f"only {len(capture['comments'])} comments (minimum {MIN_COMMENTS})")
    if len(users) < MIN_USERS:
        msgs.append(f"only {len(users)} users (need at least {MIN_USERS})")
    return msgs


def centrality_table(g: nx.DiGraph) -> list[dict]:
    """Degree and betweenness per user. The POST node takes part in the paths
    (it is where top-level comments point) but is left out of the ranking."""
    betw = nx.betweenness_centrality(g, normalized=True)
    in_deg = nx.in_degree_centrality(g)
    out_deg = nx.out_degree_centrality(g)
    rows = []
    for node in g.nodes:
        if node == POST:
            continue
        rows.append(
            {
                "user": node,
                "in_degree": g.in_degree(node),
                "out_degree": g.out_degree(node),
                "in_degree_c": round(in_deg[node], 3),
                "out_degree_c": round(out_deg[node], 3),
                "betweenness": round(betw[node], 3),
            }
        )
    rows.sort(key=lambda r: (r["betweenness"], r["in_degree"]), reverse=True)
    return rows


def influence_scores(rows: list[dict]) -> dict:
    """user -> (in_degree_norm, betweenness_norm, influence), each in [0, 1].
    Each centrality is divided by the thread's maximum; influence is their mean."""
    max_in = max((r["in_degree_c"] for r in rows), default=0)
    max_b = max((r["betweenness"] for r in rows), default=0)
    out = {}
    for r in rows:
        i = r["in_degree_c"] / max_in if max_in else 0.0
        b = r["betweenness"] / max_b if max_b else 0.0
        out[r["user"]] = (round(i, 3), round(b, 3), round((i + b) / 2, 3))
    return out


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_thread.json"
    with open(path, encoding="utf-8") as f:
        capture = json.load(f)

    g = build_graph(capture)
    print(f"graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    for w in thread_checks(capture):
        print("WARNING:", w)

    print(f"\n{'user':<22}{'in':>4}{'out':>5}{'in_c':>8}{'out_c':>8}{'betw':>8}")
    for r in centrality_table(g):
        print(
            f"{r['user']:<22}{r['in_degree']:>4}{r['out_degree']:>5}"
            f"{r['in_degree_c']:>8}{r['out_degree_c']:>8}{r['betweenness']:>8}"
        )
