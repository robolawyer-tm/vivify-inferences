#!/usr/bin/env python3
"""Parity check: fused logos pass (logos_fused.py, 1 call) vs the per-operator path
(logos_operator.py, 8 calls), WITH a same-path control.

The fused pass trades 8 focused calls for 1 combined call. This measures whether that
discount costs per-dimension accuracy — and it is the check that decides whether the
fused path (which every field run uses) can be trusted to re-derive the store.

THE CONTROL IS THE POINT. These operators call `claude -p`, which exposes no sampling
knob, so two runs of the SAME path already disagree. Comparing per-op against fused
once and reporting the difference would attribute sampling noise to fusion — the exact
false positive the order-dependence experiment documented (see
new_material/outside_view_experiment/order_dependence/FINDINGS.md §1). So each path is
run twice and three arms are reported:

    same-path (per-op)   po1 vs po2      }  the noise floor
    same-path (fused)    fu1 vs fu2      }
    cross-path           po x fu, all 4 pairings averaged

A fusion effect exists only if cross-path disagreement EXCEEDS the same-path floor.

Two inferences at 18 calls each (8+8 per-op, 1+1 fused) at VIVIFY_VOTES=1.
Run public-only with the gate relaxed:

    PRIVACY_GATE=off VIVIFY_VOTES=1 python3 tests/check_fused_parity.py [N]

Exit 1 when the harness verified nothing, or when cross-path disagreement clears the
same-path floor. Never writes the store.
"""
import sys
import copy
import itertools
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from vivify_core import read_json, resolve_model, LLMUnavailable, _vote_count

import logos_operator
import logos_fused

# Reference inferences are SELECTED AT RUNTIME, not hardcoded. The three paths that
# used to live here (agentic_self_evolution/, adaptive_equilibrium/,
# ai_workflow_comprehension/ under api_output/) were made stale by the July
# flat-by-domain store reorganisation. read_json returns {} for a missing file, so
# every one was reported as "no raw_text, skipped" and the check exited 0 having
# compared nothing — green, and verifying nothing, from July until 2026-09-06.
#
# Excludes the legal field: those carry sensitive=True field data and this check is
# meant to be runnable on public material.
REF_GLOB = "inferences/**/inf_*.json"
REF_EXCLUDE = ("inferences/field/",)

# logos dimension -> primary field(s) to compare.
# scale added 2026-09-06. It was omitted, which mattered: scale is the field
# cross_scale keys every link on (a link REQUIRES the two scales to differ), it is the
# least stable field in the 09-03 re-read, and the one place a fused/per-op
# disagreement had been observed on real field data (Washington: fused=global,
# per-op=institution). The check that should have caught that was not comparing it.
DIMS = [
    ("act_type",     ["value"]),
    ("cooperative",  ["status"]),
    ("transmission", ["value"]),
    ("resonance",    ["value"]),
    ("authority",    ["value"]),
    ("utility",      ["value"]),
    ("social_field", ["quadrant"]),
    ("structural",   ["scale", "density", "persistence", "authority",
                      "transmission", "memory_channel", "language_mode"]),
]


def pick_refs(n):
    """Pick n usable reference inferences: present, public, with real raw_text."""
    found = []
    for path in sorted(ROOT.glob(REF_GLOB)):
        rel = path.relative_to(ROOT).as_posix()
        if any(rel.startswith(x) for x in REF_EXCLUDE):
            continue
        ref = read_json(path)
        if len(ref.get("raw_text") or "") < 200:      # too short to exercise 8 dims
            continue
        found.append((rel, ref))
        if len(found) == n:
            break
    return found


def flatten(tagged):
    """{dim.field: value} for the compared fields of one run."""
    logos = tagged.get("logos", {})
    return {f"{dim}.{f}": (logos.get(dim) or {}).get(f)
            for dim, fields in DIMS for f in fields}


def disagreements(a, b):
    """Fields where two runs differ, as {field: (a, b)}."""
    return {k: (a.get(k), b.get(k)) for k in a.keys() | b.keys() if a.get(k) != b.get(k)}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    model = resolve_model("logos_operator")
    print(f"Parity WITH same-path control | model={model} | votes={_vote_count()} "
          f"| {n} inference(s)\n")

    refs = pick_refs(n)
    if not refs:
        print(f"FAILED: no usable reference inference found under {REF_GLOB}")
        sys.exit(1)

    same_po, same_fu, cross, nfields = [], [], [], 0
    divergent = set()

    for ref_path, ref in refs:
        print(f"=== {ref_path}")
        print(f"    {ref['raw_text'][:88]!r}")
        try:
            po = [flatten(logos_operator.run(copy.deepcopy(ref))) for _ in range(2)]
            fu = [flatten(logos_fused.run(copy.deepcopy(ref))) for _ in range(2)]
        except LLMUnavailable as e:
            print(f"\n    LLM unavailable (quota/auth?): {e}")
            print("    Stopping — re-run in the next window.\n")
            break

        nfields = len(po[0])
        d_po = disagreements(po[0], po[1])
        d_fu = disagreements(fu[0], fu[1])
        d_x = [disagreements(p, f) for p, f in itertools.product(po, fu)]

        same_po.append(len(d_po))
        same_fu.append(len(d_fu))
        cross.extend(len(d) for d in d_x)

        print(f"    same-path per-op : {len(d_po)}/{nfields} differ  "
              f"{sorted(d_po) if d_po else ''}")
        print(f"    same-path fused  : {len(d_fu)}/{nfields} differ  "
              f"{sorted(d_fu) if d_fu else ''}")
        print(f"    cross-path       : {[len(d) for d in d_x]} differ "
              f"(4 pairings), mean {sum(len(d) for d in d_x)/4:.2f}")
        # The load-bearing statistic. A field is PATH-DIVERGENT when it differs in
        # every cross pairing AND is stable within each path — each path agreeing
        # with itself and disagreeing with the other. That is a path effect;
        # a field that merely wobbles cannot produce it.
        persistent = set.intersection(*[set(d) for d in d_x]) if d_x else set()
        persistent = {k for k in persistent
                      if po[0].get(k) == po[1].get(k) and fu[0].get(k) == fu[1].get(k)}
        divergent.update(persistent)
        if persistent:
            print(f"    differs in ALL 4 cross pairings: {sorted(persistent)}")
            for k in sorted(persistent):
                print(f"        {k}: per-op={po[0].get(k)!r} / {po[1].get(k)!r}   "
                      f"fused={fu[0].get(k)!r} / {fu[1].get(k)!r}")
        print()

    if not cross:
        # A check that compared nothing must NOT report success. This is the guard
        # whose absence let the stale paths above go unnoticed for two months.
        print("FAILED: no comparisons made — no calls completed.")
        sys.exit(1)

    same_all = same_po + same_fu
    same_mean, cross_mean = sum(same_all) / len(same_all), sum(cross) / len(cross)
    floor = max(same_all)

    print("=" * 64)
    print(f"fields compared per run : {nfields}")
    print(f"same-path disagreement  : mean {same_mean:.2f}  (per-op {same_po}, fused {same_fu})")
    print(f"cross-path disagreement : mean {cross_mean:.2f}  {cross}")
    print()
    # Means alone are the WRONG verdict statistic, and reported a false negative on
    # 2026-09-06: pooling across inferences washed out two fields that differed in
    # every cross pairing while each path agreed with itself. Averages hide a
    # systematic disagreement behind an unaffected second inference. The
    # path-divergent field count is the verdict; the means stay as context.
    if divergent:
        print(f"VERDICT: {len(divergent)} PATH-DIVERGENT field(s) — "
              f"{', '.join(sorted(divergent))}")
        print("Each path agrees with itself and disagrees with the other on these, so "
              "this is a fusion effect, not sampling noise.")
        print("The fused path is what field runs use — these fields are what the store "
              "holds, and the per-operator path would give something else.")
        sys.exit(1)
    print(f"VERDICT: no path-divergent fields. Cross-path mean {cross_mean:.2f} vs "
          f"same-path floor {floor}.")
    print("This does NOT prove the paths agree; it says no field disagreed "
          "systematically at this sample size.")


if __name__ == "__main__":
    main()

# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/tests/check_fused_parity.py | new: fused-vs-per-operator parity check on public refs, same model both sides, to decide if the 8->1 fused logos call is a safe drop-in before trusting it on real data
# llm: claude-opus-5 | 2026-09-06 | repos/vivify-operators/tests/check_fused_parity.py | fixed a vacuous check: the three hardcoded refs went stale in the July store reorg, read_json returned {} for each, and the run exited 0 having compared nothing. Refs now selected at runtime (public, >=200 chars raw_text); zero comparisons exits 1
# llm: claude-opus-5 | 2026-09-06 | repos/vivify-operators/tests/check_fused_parity.py | added structural.scale to the compared fields, and a SAME-PATH CONTROL (each path run twice) — without it a single cross-path diff attributes sampling noise to fusion, the false positive the order-dependence experiment documented
# llm: claude-opus-5 | 2026-09-06 | repos/vivify-operators/tests/check_fused_parity.py | verdict now counts PATH-DIVERGENT fields (differ in all 4 cross pairings while stable within each path) instead of comparing means — the mean criterion returned a false negative on its first real run, pooling away authority.value and utility.value which diverged systematically
