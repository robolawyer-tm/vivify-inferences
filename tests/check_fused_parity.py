#!/usr/bin/env python3
"""Parity check: fused logos pass (logos_fused.py, 1 call) vs the per-operator path
(logos_operator.py, 8 calls), on the SAME model and the SAME public inferences.

The fused pass trades 8 focused calls for 1 combined call — this measures whether
that costs per-dimension accuracy. For each reference inference it runs BOTH paths
on in-memory copies (never writes the store) and compares the primary coordinate
field(s) of each of the 8 logos dimensions. Same model both sides, so any gap is the
fusion effect, not the model.

Makes real claude calls (9 per inference: 8 per-op + 1 fused). Run public-only with
the gate relaxed:  PRIVACY_GATE=off python3 tests/check_fused_parity.py [N]
(N = how many reference inferences to test, default 2, to stay inside a quota window).
"""
import sys
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from vivify_core import read_json, resolve_model, LLMUnavailable

import logos_operator
import logos_fused

REFS = [
    "inferences/agentic_self_evolution/api_output/inf_0bc11447.json",
    "inferences/adaptive_equilibrium/api_output/inf_72711662.json",
    "inferences/ai_workflow_comprehension/api_output/inf_58190c7d.json",
]

# logos dimension -> primary field(s) to compare for parity
DIMS = [
    ("act_type",     ["value"]),
    ("cooperative",  ["status"]),
    ("transmission", ["value"]),
    ("resonance",    ["value"]),
    ("authority",    ["value"]),
    ("utility",      ["value"]),
    ("social_field", ["quadrant"]),
    ("structural",   ["density", "persistence", "authority",
                      "transmission", "memory_channel", "language_mode"]),
]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    model = resolve_model("logos_operator")
    print(f"Parity: fused vs per-operator | model={model} | {n} inference(s)\n")

    agree = total = 0
    for ref_path in REFS[:n]:
        ref = read_json(ROOT / ref_path)
        if not ref.get("raw_text"):
            print(f"=== {ref_path}  (no raw_text, skipped)\n")
            continue
        print(f"=== {ref_path}")
        print(f"    {ref['raw_text'][:90]!r}")
        try:
            per_op = logos_operator.run(copy.deepcopy(ref))
            fused = logos_fused.run(copy.deepcopy(ref))
        except LLMUnavailable as e:
            print(f"\n    LLM unavailable (quota/auth?): {e}")
            print("    Stopping — re-run in the next window for the rest.\n")
            break

        po_logos, fu_logos = per_op.get("logos", {}), fused.get("logos", {})
        for dim, fields in DIMS:
            po, fu = po_logos.get(dim, {}), fu_logos.get(dim, {})
            for f in fields:
                a, b = po.get(f), fu.get(f)
                total += 1
                if a == b:
                    agree += 1
                else:
                    print(f"    DIFFER {dim}.{f}: per-op={a!r}  fused={b!r}")
        print()

    if total:
        print("=" * 56)
        print(f"AGREEMENT: {agree}/{total} fields = {100*agree/total:.0f}%")
        print("(100% = fused is a safe drop-in; lower = fusion is costing per-dim "
              "sharpness — keep the per-operator path for those dimensions.)")
    else:
        print("No comparisons made (no calls completed).")


if __name__ == "__main__":
    main()

# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/tests/check_fused_parity.py | new: fused-vs-per-operator parity check on public refs, same model both sides, to decide if the 8->1 fused logos call is a safe drop-in before trusting it on real data
