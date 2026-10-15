"""HTTP layer for the moderation API. Run from the backend folder:

  python -m uvicorn api.app:app --host 127.0.0.1 --port 8000

Then open http://127.0.0.1:8000/docs to try every route in the browser.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import service
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")

app = FastAPI(title="SNA moderation API (research prototype)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # the React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestBody(BaseModel):
    capture: dict  # the anonymised JSON from Alt+Shift+J
    classifier: list[dict]  # records from components 1 to 3


class DecisionBody(BaseModel):
    decision: str  # "accept" or "override"
    reviewer: str
    note: str = ""
    final_tier: str | None = None  # required for an override


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/health")
def health():
    return {"ok": True, "tiers": service.TIERS}


@app.post("/ingest")
def ingest(body: IngestBody):
    return _call(service.ingest, body.capture, body.classifier)


@app.get("/users")
def users(min_tier: str = "warning"):
    return _call(service.list_users, min_tier)


@app.get("/users/{user_id}/justification")
def justification(user_id: str):
    return _call(service.get_justification, user_id)


@app.get("/users/{user_id}/decisions")
def decisions(user_id: str):
    return service.decisions_for(user_id)


@app.post("/users/{user_id}/decisions")
def decide(user_id: str, body: DecisionBody):
    return _call(service.record_decision, user_id, body.decision, body.reviewer, body.note, body.final_tier)
