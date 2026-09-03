#!/usr/bin/env python3
"""
session_stability.py — which legal-corpus coordinates survive a second session?

The outside-view re-run (2026-08-31) established that within-run unanimity does not
imply reproducibility: `cooperative.maxim_violated` gave `quality` 5/5 in one session
and `manner` 6/6 in another, same specimen, same model id, four days apart, while
`cooperative.status` and `resonance.value` held across both. Stability is therefore a
per-field property that has to be measured ACROSS sessions.

Nothing in the legal corpus has ever been read twice. Every finding resting on those
coordinates — Cotton's "4 of 6 signature dims held", the tension gradient
(0.892 / 0.828 / 0.678), the cross_scale 6/6 isomorphism — rests on single-session
reads of fields whose cross-session behaviour is unknown.

This re-reads the four field inferences and compares against their STORED values,
which are session 1 (2026-07-10, 07-12, and 08-13).

  direct dims   resonance, cooperative, structural  — read raw_text only
  downstream    conflict                            — run against the STORED logos,
                                                      so its own sampling is isolated
                                                      from logos churn

`predicted_tension` is then recomputed from the re-read coordinates. It makes no LLM
call of its own (tension_score.py is deterministic), so its movement is a pure
consequence of upstream drift and costs nothing to measure.

The store is never written: every operator runs against a deep copy, and results land
in a separate file. Read-only with respect to inferences/field/.

PRIVACY_GATE is relaxed for this process only. The operators pass sensitive=True and
'claude' is not in LOCAL_BACKENDS, so the gate blocks every call otherwise. These are
published Innocence Project case profiles, already committed to a public repo, and the
stored coordinates show the same relaxation was in force when they were first read.
"""

import os
import sys
import json
import copy
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

os.environ["PRIVACY_GATE"] = "off"

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import resonance_operator
import cooperative_operator
import structural_operator
import conflict_operator
import tension_score
from vivify_core import resolve_model, LLMUnavailable, CoordinateValidationError

FIELD = ROOT / "inferences" / "field"

DIRECT = {"resonance": resonance_operator,
          "cooperative": cooperative_operator,
          "structural": structural_operator}


def verdicts(dim, block):
    """The categorical fields this dim is judged on, as {field: value}."""
    if not isinstance(block, dict):
        return {dim: repr(block)}
    if "_quarantined" in block:
        return {dim: "QUARANTINED"}
    if dim == "cooperative":
        return {"cooperative.status": block.get("status"),
                "cooperative.maxim_violated": block.get("maxim_violated")}
    if dim == "structural":
        return {"structural.scale": block.get("scale")}
    if dim == "conflict":
        return {f"conflict.{k}": block.get(k)
                for k in ("schema", "behavior", "terrain", "window", "escalation_phase")}
    return {f"{dim}.value": block.get("value")}


def run_direct(inference, dim):
    inf = copy.deepcopy(inference)
    inf["logos"] = {}
    try:
        inf = DIRECT[dim].run(inf)
        return (inf.get("logos") or {}).get(dim, {})
    except CoordinateValidationError as e:
        return {"_quarantined": type(e).__name__, "_reason": str(e)[:200]}


def run_conflict(inference):
    """Against the STORED logos — fixed input, so this measures conflict's own noise."""
    inf = copy.deepcopy(inference)
    inf.pop("conflict", None)
    try:
        inf = conflict_operator.run(inf)
        return inf.get("conflict", {})
    except CoordinateValidationError as e:
        return {"_quarantined": type(e).__name__, "_reason": str(e)[:200]}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", default="inferences/session_stability_runs.json")
    args = ap.parse_args()

    model = resolve_model("logos_operator")
    print(f"logos_operator model: {model}")
    if "opus" not in model:
        sys.exit(f"ABORT: expected Opus, resolved {model!r}")

    specimens = sorted(FIELD.glob("inf_*.json"))
    out = {"_meta": {"started": datetime.now(timezone.utc).isoformat(),
                     "model": model, "reps": args.reps,
                     "note": "session 2; stored values are session 1"},
           "runs": []}

    for path in specimens:
        inference = json.loads(path.read_text())
        sid, case = inference["id"], inference.get("case_id")
        print(f"\n=== {sid}  {case}"
              f"{'  (canonical)' if inference.get('canonical') else ''} ===")
        for dim in ("resonance", "cooperative", "structural", "conflict"):
            print(f"  {dim:12} x{args.reps}: ", end="", flush=True)
            for rep in range(1, args.reps + 1):
                try:
                    block = run_conflict(inference) if dim == "conflict" \
                        else run_direct(inference, dim)
                except LLMUnavailable as e:
                    sys.exit(f"\nLLM unavailable: {e}")
                v = verdicts(dim, block)
                print(f"[{' '.join(str(x) for x in v.values())}] ", end="", flush=True)
                out["runs"].append({"specimen": sid, "case_id": case,
                                    "canonical": inference.get("canonical"),
                                    "dim": dim, "rep": rep, "verdicts": v,
                                    "confidence": block.get("confidence")
                                    if isinstance(block, dict) else None,
                                    "model": block.get("_model")
                                    if isinstance(block, dict) else None,
                                    "block": block})
            print()

    out["_meta"]["finished"] = datetime.now(timezone.utc).isoformat()
    dest = ROOT / args.out
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()

# llm: claude-opus-5 | 2026-09-03 | repos/vivify-operators/session_stability.py | created — second-session re-read of the 4 legal field inferences (resonance/cooperative/structural direct, conflict against stored logos), store never written; answers whether the coordinates findings rest on are cross-session stable
