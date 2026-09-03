#!/usr/bin/env python3
"""
session_stability_report.py — compare the second-session re-read against the store.

Reads session_stability_runs.json (session 2) and inferences/field/ (session 1) and
reports, per field: whether session 2 was internally unanimous, whether it AGREES with
the stored value, and therefore which coordinates are safe to build a finding on.

Also recomputes predicted_tension under the session-2 coordinates. tension_score.py
makes no LLM call, so any movement there is a pure downstream consequence of the drift
measured above — the gradient (0.892 / 0.828 / 0.678) is only as stable as its inputs.
"""

import sys
import json
import argparse
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))
import tension_score

FIELD = ROOT / "inferences" / "field"


def stored_value(inf, field):
    """Pull the session-1 value for a dotted field name."""
    dim, _, leaf = field.partition(".")
    if dim == "conflict":
        return (inf.get("conflict") or {}).get(leaf)
    block = (inf.get("logos") or {}).get(dim) or {}
    if dim == "cooperative":
        return block.get(leaf)
    if dim == "structural":
        return block.get("scale")
    return block.get("value")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="inferences/session_stability_runs.json")
    args = ap.parse_args()
    data = json.loads((ROOT / args.runs).read_text())

    stored = {}
    for p in FIELD.glob("inf_*.json"):
        j = json.loads(p.read_text())
        stored[j["id"]] = j

    by = {}
    for r in data["runs"]:
        for field, value in r["verdicts"].items():
            by.setdefault((r["specimen"], field), []).append(value)

    print(f"model: {data['_meta']['model']}   reps: {data['_meta']['reps']}")
    print("session 1 = stored values (2026-07-10 / 07-12 / 08-13); session 2 = this run\n")

    hdr = f"{'case':<18} {'field':<28} {'session 1':<14} {'session 2':<22} {'':<10}"
    print(hdr); print("-" * len(hdr))

    tally = Counter()
    for sid in sorted(stored, key=lambda s: (stored[s].get("case_id") or "", s)):
        inf = stored[sid]
        label = (inf.get("case_id") or sid)[:16] + ("*" if inf.get("canonical") else "")
        fields = [f for (s, f) in by if s == sid]
        if not fields:
            continue
        for field in sorted(fields):
            vals = by[(sid, field)]
            c = Counter(vals)
            s1 = stored_value(inf, field)
            unanimous = len(c) == 1
            s2 = c.most_common(1)[0][0]
            disp = str(s2) if unanimous else ", ".join(f"{v}x{n}" for v, n in c.most_common())
            if not unanimous:
                verdict = "SPLIT"
            elif s2 == s1:
                verdict = "stable"
            else:
                verdict = "** FLIPPED **"
            tally[verdict] += 1
            print(f"{label:<18} {field:<28} {str(s1):<14} {disp:<22} {verdict}")
        print()

    print(f"totals: {dict(tally)}\n")

    # ---- downstream: predicted tension under session-2 coordinates ----
    print("predicted_tension — deterministic, so this is pure downstream consequence")
    print(f"{'case':<18} {'stored':>8} {'session 2':>11} {'delta':>8}")
    print("-" * 48)
    for sid in sorted(stored, key=lambda s: (stored[s].get("case_id") or "", s)):
        inf = stored[sid]
        fields = [f for (s, f) in by if s == sid]
        if not fields:
            continue
        rebuilt = json.loads(json.dumps(inf))
        for field in fields:
            vals = Counter(by[(sid, field)]).most_common(1)[0][0]
            dim, _, leaf = field.partition(".")
            if dim == "conflict":
                rebuilt.setdefault("conflict", {})[leaf] = vals
            elif dim == "structural":
                rebuilt["logos"].setdefault("structural", {})["scale"] = vals
            elif dim == "cooperative":
                rebuilt["logos"].setdefault("cooperative", {})[leaf] = vals
            else:
                rebuilt["logos"].setdefault(dim, {})["value"] = vals
        old = tension_score.predicted_tension(inf)
        new = tension_score.predicted_tension(rebuilt)
        label = (inf.get("case_id") or sid)[:16] + ("*" if inf.get("canonical") else "")
        d = "—" if (old is None or new is None) else f"{new - old:+.4f}"
        print(f"{label:<18} {str(old):>8} {str(new):>11} {d:>8}")
    print("\n* = canonical telling")


if __name__ == "__main__":
    main()

# llm: claude-opus-5 | 2026-09-03 | repos/vivify-operators/session_stability_report.py | created — stored-vs-rerun comparator for the legal corpus; flags per-field stable/FLIPPED/SPLIT and propagates the drift through the deterministic predicted_tension
