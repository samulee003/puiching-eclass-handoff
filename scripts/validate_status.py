#!/usr/bin/env python3
"""Validate status.json against schema/status.schema.json.

Also performs a couple of contract checks that a plain JSON Schema cannot express:
- every item `due` must be a real calendar date;
- `updated_at` must be a parseable timestamp.

Exit code 0 on success, 1 on any validation error.
"""
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATUS = ROOT / "status.json"
SCHEMA = ROOT / "schema" / "status.schema.json"


def fail(msg: str) -> None:
    print(f"::error::{msg}")


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        fail("jsonschema is not installed. Run: pip install jsonschema")
        return 1

    try:
        data = json.loads(STATUS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"{STATUS} not found")
        return 1
    except json.JSONDecodeError as exc:
        fail(f"status.json is not valid JSON: {exc}")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    errors = []

    validator = jsonschema.Draft7Validator(schema)
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "(root)"
        errors.append(f"schema: at {loc}: {err.message}")

    # Semantic checks beyond the schema.
    updated_at = data.get("updated_at", "")
    try:
        datetime.datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        errors.append(f"updated_at is not a valid timestamp: {updated_at!r}")

    sections = ("due_today", "due_soon", "tests_this_week", "other")
    for child in data.get("children", []):
        cid = child.get("id", "?")
        for sec in sections:
            for it in child.get(sec, []):
                due = it.get("due", "")
                try:
                    datetime.date.fromisoformat(due)
                except (ValueError, TypeError):
                    title = it.get("title", "?")
                    errors.append(
                        f"child {cid} / {sec}: item {title!r} has invalid due date {due!r}"
                    )

    if errors:
        print(f"status.json validation FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    n_children = len(data.get("children", []))
    n_items = sum(
        len(c.get(s, [])) for c in data.get("children", []) for s in sections
    )
    print(f"status.json is valid: {n_children} child record(s), {n_items} homework item(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
