#!/usr/bin/env python3
"""Validate llama3:8b operator classification quality against the coordinate enums.

For each public reference inference (already tagged on Haiku/Sonnet), re-run every
operator through the currently-routed local model on an in-memory COPY (never writes
the store) and report two signals per operator:

  in-enum  — run() did NOT raise CoordinateValidationError, i.e. the local model's
             output passed the validation gate (config/coordinates.json). The slip test.
  parity   — the local model's primary enum field matches the Haiku/Sonnet reference.

Run from the vivify-operators dir:  python3 tests/validate_local_model.py
"""
import sys
import copy
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from vivify_core import read_json, CoordinateValidationError, resolve_model, LLMUnavailable

# Public reference inferences only (skip inferences/private/* — real legal material).
REFS = [
    "inferences/agentic_self_evolution/api_output/inf_0bc11447.json",
    "inferences/adaptive_equilibrium/api_output/inf_72711662.json",
    "inferences/ai_workflow_comprehension/api_output/inf_58190c7d.json",
]

# operator module -> (subtree, primary enum field(s) to compare for parity)
OPS = [
    ("act_type_operator",     ("logos", "act_type"),     ["value"]),
    ("authority_operator",    ("logos", "authority"),    ["value"]),
    ("cooperative_operator",  ("logos", "cooperative"),  ["status"]),
    ("resonance_operator",    ("logos", "resonance"),    ["value"]),
    ("social_field_operator", ("logos", "social_field"), ["quadrant"]),
    ("transmission_operator", ("logos", "transmission"), ["value"]),
    ("utility_operator",      ("logos", "utility"),      ["value"]),
    ("structural_operator",   ("logos", "structural"),
     ["density", "persistence", "authority", "transmission", "memory_channel", "language_mode"]),
    ("conflict_operator",     ("conflict",),
     ["schema", "behavior", "terrain", "window", "escalation_phase"]),
]


def subtree(d, path):
    for k in path:
        d = (d or {}).get(k, {})
    return d or {}


def main():
    print(f"Local model in use: logos_operator -> {resolve_model('logos_operator')} | "
          f"conflict_operator -> {resolve_model('conflict_operator')}\n")
    tallies = {op[0]: {"in_enum": 0, "slip": 0, "err": 0, "match": 0, "diff": 0, "n": 0}
               for op in OPS}

    for ref_path in REFS:
        ref = read_json(ROOT / ref_path)
        print(f"=== {ref_path}")
        print(f"    { (ref.get('raw_text','') or '')[:90]!r}\n")
        for mod_name, where, fields in OPS:
            mod = importlib.import_module(mod_name)
            fresh = copy.deepcopy(ref)
            t = tallies[mod_name]
            t["n"] += 1
            try:
                out = mod.run(fresh)
            except CoordinateValidationError as e:
                t["slip"] += 1
                print(f"    {mod_name:22s} SLIP (out-of-enum): {str(e)[:80]}")
                continue
            except (LLMUnavailable, Exception) as e:
                t["err"] += 1
                print(f"    {mod_name:22s} ERROR: {type(e).__name__}: {str(e)[:70]}")
                continue
            t["in_enum"] += 1
            got = subtree(out, where)
            exp = subtree(ref, where)
            diffs = []
            for f in fields:
                g, x = got.get(f), exp.get(f)
                if g == x:
                    t["match"] += 1
                else:
                    t["diff"] += 1
                    diffs.append(f"{f}: {x!r}->{g!r}")
            flag = "MATCH" if not diffs else "DIFFER"
            detail = "" if not diffs else "  " + "; ".join(diffs)
            print(f"    {mod_name:22s} in-enum OK | {flag}{detail}")
        print()

    print("=== SUMMARY (across", len(REFS), "inferences) ===")
    print(f"{'operator':22s} {'in-enum':>8s} {'slip':>5s} {'err':>4s} | {'field match':>12s}")
    g_in = g_slip = g_match = g_fields = 0
    for mod_name, _, _ in OPS:
        t = tallies[mod_name]
        fields_total = t["match"] + t["diff"]
        print(f"{mod_name:22s} {t['in_enum']:>4d}/{t['n']:<3d} {t['slip']:>5d} {t['err']:>4d} | "
              f"{t['match']:>5d}/{fields_total:<6d}")
        g_in += t["in_enum"]; g_slip += t["slip"]; g_match += t["match"]; g_fields += fields_total
    total = sum(t["n"] for t in tallies.values())
    print("-" * 56)
    print(f"{'TOTAL':22s} {g_in:>4d}/{total:<3d} {g_slip:>5d} {'':>4s} | {g_match:>5d}/{g_fields:<6d}")
    print(f"\nin-enum rate (gate pass): {g_in}/{total} = {100*g_in/total:.0f}%")
    print(f"parity with Haiku/Sonnet: {g_match}/{g_fields} = {100*g_match/g_fields:.0f}% of enum fields")


if __name__ == "__main__":
    main()
