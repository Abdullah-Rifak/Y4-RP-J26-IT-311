"""The live path between the extension, the API and the classifiers.

  extension     --POST /capture-------------> store the thread, score it with what is known so far
  classifiers   --GET  /pending--------------> comments that still need a label
  classifiers   --POST /classifications-----> store their labels, re-score the affected posts

Either side can go first: a post is re-scored whenever new comments or new labels arrive, and
re-scoring replaces the post's old entry, so nothing is ever counted twice.
Only the four contract fields of a classifier record are kept (no text is copied into them).
"""
import json

from api import service
from risk_scoring.risk import thread_contributions, update_store
from risk_scoring.severity import REQUIRED, attach, validate

CAPTURES = "capture_store.json"  # post_id -> the anonymised capture
CLASSIFIER = "classifier_store.json"  # comment_id -> records, one per source component


# paths are looked up at call time, so tests can point service.DATA_DIR somewhere else
def _load(name: str, default):
    p = service.DATA_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _save(name: str, obj) -> None:
    service.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (service.DATA_DIR / name).write_text(json.dumps(obj), encoding="utf-8")


def check_capture(capture) -> None:
    if not isinstance(capture, dict) or not isinstance(capture.get("post_id"), str) or not capture["post_id"]:
        raise ValueError("the capture has no post_id: open the post on its own page and capture again")
    if not isinstance(capture.get("comments"), list):
        raise ValueError("the capture needs a list of comments")
    for i, c in enumerate(capture["comments"]):
        missing = [k for k in ("comment_id", "author_id", "type") if k not in c]
        if missing:
            raise ValueError(f"comment {i} is missing {missing}")


def _rescore(post_id: str, captures: dict, cstore: dict, store: dict) -> dict:
    cap = captures[post_id]
    records = [r for c in cap["comments"] for r in cstore.get(c["comment_id"], [])]
    scored = attach(cap, records)
    contribs = thread_contributions(cap, scored)
    update_store(store, post_id, contribs)
    return {"post_id": post_id, "comments": len(cap["comments"]),
            "unclassified": sum(1 for s in scored if s["severity"] is None),
            "users_flagged": len(contribs),
            "centrality_applied": any(c["centrality_applied"] for c in contribs.values()) if contribs else None}


def store_capture(capture: dict) -> dict:
    check_capture(capture)
    with service._lock:
        captures = _load(CAPTURES, {})
        captures[capture["post_id"]] = capture  # a re-capture replaces the earlier one
        _save(CAPTURES, captures)
        store = service.load_store()
        summary = _rescore(capture["post_id"], captures, _load(CLASSIFIER, {}), store)
        service.save_store(store)
    return summary


def add_classifications(records: list[dict]) -> dict:
    if not isinstance(records, list) or not records:
        raise ValueError("send a non-empty list of classifier records")
    validate(records)  # nothing is stored if any record is bad
    with service._lock:
        cstore = _load(CLASSIFIER, {})
        for r in records:
            kept = [x for x in cstore.get(r["comment_id"], []) if x["source_component"] != r["source_component"]]
            cstore[r["comment_id"]] = kept + [{k: r[k] for k in REQUIRED}]  # a source's newer label replaces its older one
        _save(CLASSIFIER, cstore)
        captures = _load(CAPTURES, {})
        ids = {r["comment_id"] for r in records}
        affected = [pid for pid, cap in captures.items() if any(c["comment_id"] in ids for c in cap["comments"])]
        store = service.load_store()
        for pid in affected:
            _rescore(pid, captures, cstore, store)
        service.save_store(store)
    return {"records": len(records), "posts_rescored": affected}


def pending(kind: str | None = None, source: str | None = None, limit: int = 100) -> list[dict]:
    """Comments that still need a label. kind: 'text' or 'media' narrows to comments that have
    that content. source: only comments this component has not labelled yet (without it, only
    comments nobody has labelled). Gives the classifier what it needs and nothing else: no author."""
    if kind not in (None, "text", "media"):
        raise ValueError("kind must be 'text' or 'media'")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    captures, cstore = _load(CAPTURES, {}), _load(CLASSIFIER, {})
    out = []
    for pid, cap in captures.items():
        for c in cap["comments"]:
            recs = cstore.get(c["comment_id"], [])
            if (any(r["source_component"] == source for r in recs) if source else bool(recs)):
                continue
            text, media = c.get("text"), c.get("media") or []
            if (kind == "text" and not text) or (kind == "media" and not media):
                continue
            out.append({"comment_id": c["comment_id"], "post_id": pid, "text": text, "media": media})
            if len(out) >= limit:
                return out
    return out
