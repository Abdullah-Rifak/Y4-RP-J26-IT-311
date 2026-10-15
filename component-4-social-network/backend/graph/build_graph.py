"""Stage 2 of 6: build the interaction graph for one captured thread.

Input : the anonymised JSON copied with Alt+Shift+J in the extension.
Graph : directed. Nodes = pseudonymous users plus one POST node.
        Edge A -> B means "A replied to / mentioned B".
        A top-level comment is an edge from the author to the POST node.

Usage (from the backend folder):  python -m graph.build_graph data/sample_thread.json
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


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_thread.json"
    with open(path, encoding="utf-8") as f:
        g = build_graph(json.load(f))
    print(f"graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    for src, dst, d in g.edges(data=True):
        print(f"  {src} -> {dst}  (x{d['weight']})")
