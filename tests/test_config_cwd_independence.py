#!/usr/bin/env python3
"""Focused test: config resolution does not depend on the current directory.

Regression guard. `resolve_model` and `_load_coordinates` used to read
Path("config")/... — relative to the CWD — while `read_json` returns {} for a
missing file. Running an operator from anywhere but the repo root therefore failed
twice, silently:

  - model_map.json not found  -> every capability fell through to the hardcoded
    claude-sonnet-4-6, so the mapped Opus model was quietly downgraded
  - coordinates.json not found -> the spec went empty, so op_spec was empty and the
    enum/range gate accepted anything ({"status": "BANANA", "confidence": 47.5}
    validated clean and could enter the store)

Neither left a trace. The other test modules all os.chdir(ROOT) before importing,
which is exactly why this went unnoticed — so this module deliberately does not.

No real LLM calls.

Run standalone: python3 tests/test_config_cwd_independence.py  (exit 0 = pass)
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))
# NOTE: no os.chdir(ROOT) here — running from elsewhere is the whole point.

import vivify_core
from vivify_core import (read_json, resolve_model, validate_coordinates,
                         CoordinateValidationError)

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}" + (f" — {detail}" if detail else ""))
        failures.append(label)


MAP = read_json(ROOT / "config" / "model_map.json")
SPEC = read_json(ROOT / "config" / "coordinates.json")
COOP_ENUM = SPEC["operators"]["cooperative"]["enums"]["status"]

# Somewhere with no config/ of its own — the condition that used to break things.
foreign = tempfile.mkdtemp(prefix="vivify_cwd_test_")

print(f"model_map default: {MAP.get('default')}")
print(f"logos_operator   : {MAP.get('logos_operator')}")
print(f"foreign cwd      : {foreign}\n")

for cwd in (ROOT, Path(foreign), Path("/")):
    os.chdir(cwd)
    where = "repo root" if cwd == ROOT else str(cwd)
    print(f"cwd = {where}")

    # 1. the mapped model survives, rather than falling through to the default
    for capability in ("logos_operator", "conflict_operator", "semantic_extraction"):
        expected = MAP[capability]
        got = resolve_model(capability)
        check(f"resolve_model({capability}) -> {expected}", got == expected,
              f"got {got}")

    # 2. the enum gate is live, not silently empty
    try:
        validate_coordinates({"status": "BANANA"}, "cooperative")
        check("enum gate rejects out-of-enum status", False,
              "accepted 'BANANA' — spec did not load")
    except CoordinateValidationError as e:
        check("enum gate rejects out-of-enum status", "BANANA" in str(e))

    # 3. and it still passes a legitimate coordinate
    ok = {"status": COOP_ENUM[1], "maxim_violated": "quality", "confidence": 0.8}
    try:
        check("valid coordinate still accepted",
              validate_coordinates(dict(ok), "cooperative") == ok)
    except CoordinateValidationError as e:
        check("valid coordinate still accepted", False, str(e))
    print()

# 4. an absolute config_dir is still honored as given
os.chdir(foreign)
check("absolute config_dir honored",
      vivify_core._config_path(str(ROOT / "config"), "model_map.json")
      == ROOT / "config" / "model_map.json")

# 5. a relative config_dir anchors to the repo root, not the cwd
check("relative config_dir anchors to repo root",
      vivify_core._config_path("config", "model_map.json")
      == ROOT / "config" / "model_map.json")

os.chdir(ROOT)
os.rmdir(foreign)

print()
if failures:
    print(f"FAILED: {len(failures)} check(s) — {', '.join(failures)}")
    sys.exit(1)
print("All cwd-independence checks passed.")

# llm: claude-opus-5 | 2026-08-27 | repos/vivify-operators/tests/test_config_cwd_independence.py | created — regression guard: model_map + coordinates spec must resolve from any cwd (silent model downgrade + disabled enum gate)
