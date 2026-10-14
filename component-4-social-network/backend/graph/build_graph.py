"""Build the interaction graph for one captured thread and compute centrality.

Usage:  python graph/build_graph.py data/sample_thread.json

Input  : the anonymised JSON copied with Alt+Shift+J in the extension.
Graph  : directed. Nodes = pseudonymous users plus one POST node.
         Edge A -> B means "A replied to / mentioned B".
         A top-level comment is an edge from the author to the POST node.
"""
import json
import sys
from collections import Counter

import networkx as nx

POST = "POST"  # synthetic node standing for the post itself


def build_graph(capture: dict) -> nx.DiGraph:
    comments = capture["comments"]
    by_id = {c["comment_id"]: c for c in comments}
    edges = Counter()  # (src, dst) -> number of interactions

    for c in comments:
        src = c["author_id"]
        if not src:
            continue

        targets = set()
        if c["type"] == "comment":
            targets.add(POST)
        else:
            dst = c.get("reply_to_id")
            if not dst:
                # Target name was ambiguous or its comment wasn't captured:
                # fall back to the author of the thread's root comment.
                root = by_id.get(c.get("thread_root_id"))
                dst = root["author_id"] if root else POST
            targets.add(dst)

        targets.update(m for m in c.get("mentions", []) if m)  # @mentions

        for dst in targets:
            if dst != src:  # ignore self-replies
                edges[(src, dst)] += 1

    g = nx.DiGraph()
    g.add_node(POST, kind="post")
    for c in comments:
        if c["author_id"]:
            g.add_node(c["author_id"], kind="user")
    for (src, dst), n in edges.items():
        g.add_edge(src, dst, weight=n)
    return g


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


def thread_checks(capture: dict) -> list[str]:
    """Warn when the thread is below the proposal's minimum size."""
    users = {c["author_id"] for c in capture["comments"] if c["author_id"]}
    msgs = []
    if len(capture["comments"]) < 15:
        msgs.append(f"only {len(capture['comments'])} comments (minimum 15)")
    if len(users) <= 5:
        msgs.append(f"only {len(users)} users (need more than 5)")
    return msgs


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
