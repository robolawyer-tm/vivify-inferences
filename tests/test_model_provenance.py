#!/usr/bin/env python3
"""Focused test: which model produced a coordinate is recorded, and switching
models is an env act rather than a config edit.

Two mechanisms, built for the model-comparison arm (Opus vs Fable on the same
texts) and useless without each other: an override that cannot outlive the shell
that set it, and a `_model` stamp so the store says which arm a telling came from.
Without the stamp two arms are indistinguishable after the fact; without the
override an experiment is a config edit somebody has to remember to revert.

No real LLM calls — transports are monkeypatched.

Run standalone: python3 tests/test_model_provenance.py  (exit 0 = pass)
"""
import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))
os.chdir(ROOT)          # incidental now — config resolves from any cwd
                        # (see tests/test_config_cwd_independence.py)

import vivify_core
from vivify_core import model_override, resolve_model, call_and_validate

import resonance_operator
import logos_fused
import right_pass

OVERRIDE_ENV = "VIVIFY_MODEL_OVERRIDE"
SPEC = vivify_core.read_json(ROOT / "config" / "coordinates.json")["operators"]

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}  {detail}")
        failures.append(label)


def set_override(value):
    if value is None:
        os.environ.pop(OVERRIDE_ENV, None)
    else:
        os.environ[OVERRIDE_ENV] = value


def block_for(op):
    """A minimal valid coordinate block: first allowed value per enum, 0.5 per float."""
    block = {field: values[0] for field, values in SPEC[op].get("enums", {}).items()}
    block.update({field: 0.5 for field in SPEC[op].get("floats", {})})
    return block


class FakeTransport:
    """Stands in for llm_call_model; records the model id it was handed."""

    def __init__(self, payload):
        self.payload = payload
        self.models = []

    def __call__(self, prompt, model, params=None, sensitive=False):
        self.models.append(model)
        return json.dumps(self.payload)


# --- the override --------------------------------------------------------------

print("model_override():")

set_override(None)
check("unset -> None", model_override("logos_operator") is None)

set_override("claude-fable-5")
check("bare form covers any capability",
      model_override("logos_operator") == "claude-fable-5"
      and model_override("fact_extraction") == "claude-fable-5")

set_override("logos_operator=claude-fable-5, conflict_operator=claude-fable-5")
check("scoped form hits named capability",
      model_override("logos_operator") == "claude-fable-5")
check("scoped form leaves others alone",
      model_override("semantic_extraction") is None,
      model_override("semantic_extraction"))

set_override("logos_operator=,garbage,=x,fact_extraction=claude-fable-5")
check("malformed entries are skipped, not raised",
      model_override("fact_extraction") == "claude-fable-5")
check("empty model for a named capability is ignored",
      model_override("logos_operator") is None)

print("\nresolve_model():")

set_override(None)
mapped = resolve_model("logos_operator")
check("falls through to the map when unset",
      mapped == vivify_core.read_json(ROOT / "config" / "model_map.json")["logos_operator"],
      mapped)

set_override("logos_operator=claude-fable-5")
check("override wins over the map", resolve_model("logos_operator") == "claude-fable-5")
check("unnamed capability keeps its mapped model",
      resolve_model("semantic_extraction") != "claude-fable-5")

# --- the stamp: per-operator path -----------------------------------------------

print("\ncall_and_validate() + operator parse():")

set_override("logos_operator=claude-fable-5")
transport = FakeTransport(block_for("resonance"))
original = vivify_core.llm_call_model
vivify_core.llm_call_model = transport
try:
    result = call_and_validate("prompt", "resonance", capability="logos_operator")
finally:
    vivify_core.llm_call_model = original

check("the call used the overridden model",
      transport.models == ["claude-fable-5"], transport.models)
check("result carries _model", result.get("_model") == "claude-fable-5",
      result.get("_model"))

inference = resonance_operator.parse(result, {"raw_text": "x"})
block = inference["logos"]["resonance"]
check("parse() lands _model in the coordinate block",
      block.get("_model") == "claude-fable-5", block.get("_model"))
check("_operator still recorded alongside it",
      block.get("_operator") == "resonance_operator.py")

# --- the stamp: fused path (the one field runs actually use) --------------------

print("\nlogos_fused (8 dims, 1 call):")

set_override("logos_operator=claude-fable-5")
fused_payload = {key: block_for(key) for key, _mod in logos_fused.LOGOS_DIMS}
transport = FakeTransport(fused_payload)
original = logos_fused.llm_call_model
logos_fused.llm_call_model = transport
try:
    tagged = logos_fused.run({"raw_text": "some field text"})
finally:
    logos_fused.llm_call_model = original

check("fused call used the overridden model",
      transport.models == ["claude-fable-5"], transport.models)
stamped = [key for key, _mod in logos_fused.LOGOS_DIMS
           if tagged["logos"].get(key, {}).get("_model") == "claude-fable-5"]
check("all 8 dimensions carry _model", len(stamped) == 8,
      f"stamped {len(stamped)}: {stamped}")

# --- the stamp: fact extraction (the ground-truth channel) ----------------------

print("\nright_pass (confirmed-tension channel):")

set_override("fact_extraction=claude-fable-5")
raw_text = "The lab claimed a one in 694,000 match. The actual figure was one in 16."
transport = FakeTransport({
    "right_facts": {"claimed_odds": {"value": 694000, "unit": "ratio",
                                     "quote": "one in 694,000"}},
    "discrepancies": [{"topic": "match_probability", "claimed": "1 in 694,000",
                       "actual": "1 in 16", "quote": "The actual figure was one in 16"}],
})
original = right_pass.llm_call_model
right_pass.llm_call_model = transport
try:
    inference = right_pass.apply_right_pass(
        {"id": "inf_test", "raw_text": raw_text, "left_keywords": []})
finally:
    right_pass.llm_call_model = original

check("fact extraction used the overridden model",
      transport.models == ["claude-fable-5"], transport.models)
check("right_pass provenance recorded",
      inference.get("right_pass", {}).get("_model") == "claude-fable-5",
      inference.get("right_pass"))
check("discrepancies still extracted",
      len(inference.get("discrepancies", [])) == 1)

set_override(None)

print()
if failures:
    print(f"FAILED: {len(failures)} check(s) — {', '.join(failures)}")
    sys.exit(1)
print("All model-provenance checks passed.")

# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/tests/test_model_provenance.py | created — VIVIFY_MODEL_OVERRIDE bare/scoped/malformed forms, _model stamp through call_and_validate + operator parse + fused path + right_pass
