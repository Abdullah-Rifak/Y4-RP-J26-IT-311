"""The comparison systems from the proposal (section 3.3) and the proposed system, all scored
from the same classifier output so that only the method differs.

  A  detection only : each post judged alone, no network context, no history.
  B  volume based   : users ranked by how many comments were flagged, ignoring influence.
  proposed          : severity x (1 + influence), accumulated across posts.

(Baseline C, per-post explanation, is judged by human reviewers, not by a score.)

A 'flagged' comment is one with severity above 0 in all three, so the difference you see
comes from the scoring method and not from what counts as hate.
"""
from collections import Counter

from risk_scoring.risk import thread_contributions, update_store, user_risk
from risk_scoring.severity import attach


def detection_only(capture: dict, records: list[dict]) -> dict:
    """Baseline A. user -> highest severity in this one post."""
    out: dict[str, float] = {}
    for s in attach(capture, records):
        if s["severity"]:
            out[s["author_id"]] = max(out.get(s["author_id"], 0.0), s["severity"])
    return out


def volume_based(posts: list[tuple[dict, list[dict]]]) -> dict:
    """Baseline B. user -> number of flagged comments over every post."""
    out: Counter = Counter()
    for capture, records in posts:
        for s in attach(capture, records):
            if s["severity"]:
                out[s["author_id"]] += 1
    return dict(out)


def proposed(posts: list[tuple[dict, list[dict]]]) -> dict:
    """The proposed risk score. user -> accumulated risk (kept in memory, no files touched)."""
    store: dict = {"users": {}}
    for capture, records in posts:
        update_store(store, capture["post_id"], thread_contributions(capture, attach(capture, records)))
    return {u: user_risk(store, u) for u in store["users"]}
