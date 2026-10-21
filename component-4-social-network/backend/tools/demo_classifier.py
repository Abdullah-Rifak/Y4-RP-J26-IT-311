"""A STAND-IN classifier for trying the whole system before the real components are ready.

It cannot judge anything. It labels a comment only if the comment contains a test marker:
    #testhate-political   #testhate-religious-0.9   #testhate-racial_ethnic   ...
(optionally followed by -confidence; the default is 0.85). Every other comment is left alone and
stays 'unclassified'. So the only comments it ever flags are ones you typed with a marker, on
your own test account. Its records are labelled source_component 'demo-marker'.

Usage (from the backend folder, with the API running):
  python -m tools.demo_classifier            # label what is pending once
  python -m tools.demo_classifier --watch    # keep checking every 5 seconds
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request

SOURCE = "demo-marker"
CATEGORIES = "racial_ethnic|religious|political|gender_based|sexual_orientation"
MARKER = re.compile(rf"#testhate-({CATEGORIES})(?:-(1(?:\.0+)?|0?\.\d+))?", re.IGNORECASE)


def classify(comment: dict) -> dict | None:
    m = MARKER.search(comment.get("text") or "")
    if not m:
        return None
    return {"comment_id": comment["comment_id"], "source_component": SOURCE,
            "predicted_category": m.group(1).lower(), "confidence_score": float(m.group(2)) if m.group(2) else 0.85}


def run_once(get, post, limit: int = 200) -> int:
    """get(path) -> parsed JSON; post(path, body) -> parsed JSON. Returns how many it labelled."""
    items = get(f"/pending?kind=text&source={SOURCE}&limit={limit}")
    records = [r for r in (classify(c) for c in items) if r]
    if records:
        post("/classifications", records)
    return len(records)


def _http(base: str):
    def get(path):
        with urllib.request.urlopen(base + path) as r:
            return json.loads(r.read())

    def post(path, body):
        req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    return get, post


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--watch", action="store_true")
    a = ap.parse_args()
    get, post = _http(a.api)
    while True:
        n = run_once(get, post)
        print(f"labelled {n} comment(s)")
        if not a.watch:
            break
        time.sleep(5)
