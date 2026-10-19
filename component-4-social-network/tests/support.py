"""Shared test setup: puts backend/ on the import path and loads the sample data files."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the component-4 folder
BACKEND = ROOT / "backend"
DATA = BACKEND / "data"
sys.path.insert(0, str(BACKEND))


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))
