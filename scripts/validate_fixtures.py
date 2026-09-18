"""
Validates every fixtures/*.json file (in any component folder) against
shared/contracts/classification-output.schema.json.

Run locally:
    pip install jsonschema
    python scripts/validate_fixtures.py
"""
import json
import sys
from pathlib import Path

from jsonschema import ValidationError, validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "shared" / "contracts" / "classification-output.schema.json"


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text())
    fixture_files = sorted(ROOT.glob("*/fixtures/*.json"))

    if not fixture_files:
        print("No fixture files found under */fixtures/*.json")
        return 0

    failures = 0
    for path in fixture_files:
        data = json.loads(path.read_text())
        try:
            validate(instance=data, schema=schema)
            print(f"OK   {path.relative_to(ROOT)}")
        except ValidationError as e:
            failures += 1
            print(f"FAIL {path.relative_to(ROOT)}: {e.message}")

    if failures:
        print(f"\n{failures} fixture(s) failed validation.")
        return 1

    print(f"\nAll {len(fixture_files)} fixture(s) valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())