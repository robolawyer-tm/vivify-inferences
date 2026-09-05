#!/usr/bin/env python3
"""
vote_stability_check.py — does repeat-and-vote actually survive a second session?

Step 1 of the stabilisation sequence. Repeat-and-vote (ac904c5) is ASSUMED to reduce
cross-session drift; this is the test. Comparing a voted read against the stored
single-draw values would compare two different methods, so the only honest control is
a voted read against an EARLIER VOTED read.

  session 1 (store)      single draw, 2026-07-10 / 07-12 / 08-13
  session 2 (VOTED_2026_09_03)  majority-of-3, recorded below
  session 3 (this run)   majority-of-3

The claim under test is narrow: voted reads agree with each other across sessions more
often than single draws did. The single-draw baseline was 4 of 36 coordinates flipped
and 6 more split (inferences/session_stability.md).

Store is never written. Results land in inferences/vote_stability_runs.json so the next
session has a voted baseline to diff against without hardcoding anything.
"""

import os
import sys
import json
import copy
import argparse
from pathlib import Path
from datetime import datetime, timezone

os.environ["PRIVACY_GATE"] = "off"

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import logos_fused
from vivify_core import _vote_count, LLMUnavailable

FIELD = ROOT / "inferences" / "field"
DIMS = ("structural", "resonance", "cooperative", "act_type", "authority",
        "transmission", "utility", "social_field")

# The 2026-09-03 voted read (12 fused calls, majority-of-3), transcribed from that run.
VOTED_2026_09_03 = {
    "inf_0f31de7a": {"structural": "institution", "resonance": "illusion",
                     "cooperative": "honored/None", "act_type": "assertive",
                     "authority": "sovereign"},
    "inf_285ae7ab": {"structural": "institution", "resonance": "illusion",
                     "cooperative": "honored/None", "act_type": "assertive",
                     "authority": "sovereign"},
    "inf_a3d99808": {"structural": "global", "resonance": "illusion",
                     "cooperative": "honored/None", "act_type": "assertive",
                     "authority": "sovereign"},
    "inf_f39647fd": {"structural": "institution", "resonance": "illusion",
                     "cooperative": "honored/None", "act_type": "assertive",
                     "authority": "sovereign"},
}


def verdict(dim, block):
    if not isinstance(block, dict):
        return None
    if dim == "structural":
        return block.get("scale")
    if dim == "cooperative":
        return f"{block.get('status')}/{block.get('maxim_violated')}"
    return block.get("value")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="inferences/vote_stability_runs.json")
    args = ap.parse_args()

    print(f"VIVIFY_VOTES = {_vote_count()}   (majority-of-N per dimension)\n")
    out = {"_meta": {"run": datetime.now(timezone.utc).isoformat(),
                     "votes": _vote_count(),
                     "compared_to": "VOTED_2026_09_03 (session 2, also voted)"},
           "results": {}}
    agree = differ = 0

    for p in sorted(FIELD.glob("inf_*.json")):
        inf = json.loads(p.read_text())
        sid = inf["id"]
        label = f"{inf.get('case_id')}{'*' if inf.get('canonical') else ''}"
        try:
            tagged = logos_fused.run(copy.deepcopy(inf))
        except LLMUnavailable as e:
            sys.exit(f"LLM unavailable: {e}")
        print(f"=== {label}  ({sid}) ===")
        out["results"][sid] = {}
        for dim in DIMS:
            block = (tagged.get("logos") or {}).get(dim, {})
            now = verdict(dim, block)
            votes = block.get("_votes") or {}
            rec = {"verdict": now,
                   "agreed": f"{votes.get('agreed')}/{votes.get('n')}",
                   "distribution": votes.get("distribution")}
            out["results"][sid][dim] = rec
            prev = VOTED_2026_09_03.get(sid, {}).get(dim)
            if prev is None:
                mark = "(no voted baseline)"
            elif str(now) == str(prev):
                mark = "agrees with 09-03"; agree += 1
            else:
                mark = f"** DIFFERS from 09-03 ({prev}) **"; differ += 1
            print(f"  {dim:14} {str(now):24} {rec['agreed']:5}  {mark}")
        print()

    out["_meta"]["voted_vs_voted"] = {"agree": agree, "differ": differ}
    print(f"voted-vs-voted across sessions: {agree} agree, {differ} differ "
          f"(single-draw baseline was 4 flipped / 6 split of 36)")
    (ROOT / args.out).write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {ROOT / args.out}")


if __name__ == "__main__":
    main()

# llm: claude-opus-5 | 2026-09-05 | repos/vivify-operators/vote_stability_check.py | created — step 1 of stabilisation: voted-vs-voted cross-session comparison, the only honest control for whether repeat-and-vote reduces drift; store never written
