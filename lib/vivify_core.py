"""
vivify_core — autovivification engine

Perl-style hash-of-hashes in Python. Builds nested JSON structures from
key paths without requiring a predefined schema. Structure emerges from data.
"""

import json
from collections import defaultdict
from pathlib import Path


def autovivify():
    """Return a deeply nestable defaultdict — the core autovivification primitive."""
    return defaultdict(autovivify)


def deep_update(base, update):
    """Merge update into base recursively, creating nested keys as needed.

    - Existing keys are updated in place, not overwritten at the top level
    - New keys are created at any depth without prior declaration
    - Leaf values (non-dict) are replaced by the incoming value
    """
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def to_dict(obj):
    """Recursively convert autovivified defaultdicts to plain dicts for serialization.

    - Required before JSON serialization — defaultdict is not JSON-serializable
    - Safe to call on plain dicts (no-op)
    - Handles arbitrary nesting depth
    """
    if isinstance(obj, defaultdict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def write_json(path, data, indent=2):
    """Write data to a JSON file, creating parent directories as needed.

    - path: str or Path
    - data: dict (will be serialized via to_dict first)
    - indent: pretty-print indent level
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(to_dict(data), f, indent=indent)


def read_json(path):
    """Read a JSON file and return as a plain dict.

    - Returns empty dict if file does not exist
    - Raises JSONDecodeError if file is malformed
    """
    path = Path(path)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    import sys
    import fileinput

    print("vivify_core — autovivification engine self-test")
    print()

    # Demo: build a nested structure from scratch
    store = autovivify()
    store["conflict"]["legal"]["perjury"] = "detected"
    store["conflict"]["legal"]["timeline"] = ["2024-01", "2024-03"]
    store["outcome"]["prediction"] = "adverse"

    result = to_dict(store)
    print(json.dumps(result, indent=2))

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/lib/vivify_core.py | created — autovivification engine, deep_update, JSON I/O
