#!/usr/bin/env python3
"""
vote_stability_check.py — does repeat-and-vote actually survive a second session?

Step 1 of the stabilisation sequence. Repeat-and-vote (ac904c5) is ASSUMED to reduce
cross-session drift; this is the test. Comparing a voted read against the stored
single-draw values would compare two different methods, so the only honest control is
a voted read against an EARLIER VOTED read.

  session 1 (store)      single draw, 2026-07-10 / 07-12 / 08-13
  session 2 (VOTED_2026_09_03)  majority-of-3, seed baseline below
  session 3+ (this run)  majority-of-3, diffed against the most recent recorded run

The claim under test is narrow: voted reads agree with each other across sessions more
often than single draws did. The single-draw baseline was 4 of 36 coordinates flipped
and 6 more split (inferences/session_stability.md) — note that 36 is NOT this run's
denominator, so compare rates, never raw counts.

WHAT IS MEASURED, and why it grew (2026-09-07):
The same-text Cotton pair (inf_f39647fd / inf_0f31de7a, identical raw_text read 16
minutes apart) shows the drift is layered — the 8 logos categoricals were identical
across both readings, while conflict.terrain, conflict.window and the tension numbers
all moved. Measuring logos alone therefore samples the calmest layer and would report
a stability that the unmeasured layers do not share. So conflict.terrain/window and
the three tension numbers are now measured too. Cost: conflict is a SECOND voted call
per inference (logos_fused.py:10 — conflict reads the logos outputs, so it cannot be
fused), which doubles the call count. --logos-only restores the cheaper original scope.
tension_score adds nothing: it is derived arithmetic, but it reads the conflict block,
so it rides along with conflict rather than standing alone.

Tension is numeric, not categorical, so it is reported as drift magnitude and kept OUT
of the agree/differ counts — folding a float into a categorical tally would need an
invented threshold.

Store is never written. Results append to inferences/vote_stability_runs.json so each
session diffs against the previous recorded run rather than a hardcoded dict; runs
accumulate, so re-running never destroys the baseline it just compared against.
"""

import os
import sys
import json
import copy
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import logos_fused
import conflict_operator
import tension_score
from vivify_core import _vote_count, LLMUnavailable

FIELD = ROOT / "inferences" / "field"
LOGOS_DIMS = ("structural", "resonance", "cooperative", "act_type", "authority",
              "transmission", "utility", "social_field")
CONFLICT_DIMS = ("terrain", "window")
# The numbers behind the two DERIVED bins. Recorded so their reproducibility can be read
# directly, and so bin edges can be re-cut later from the record rather than costing a
# fresh baseline. terrain also carries every draw's position; social_field has only the
# stored draw's floats (logos_fused keeps no per-draw numbers).
NUMBERS = {"social_field": ("grid", "group"), "terrain": ("terrain_distance",)}
TENSION_KEYS = ("predicted", "confirmed", "calibration_delta")

# The 2026-09-03 voted read (12 fused calls, majority-of-3), transcribed from that run.
# Seed baseline only — logos dimensions, and only the five that run recorded. Later runs
# diff against the previous entry in the runs file instead.
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
    if dim == "social_field":
        # grid/group are floats; quadrant is the categorical enum. Without this
        # branch the fallthrough asked for .value, which social_field never has,
        # so all four coordinates silently recorded None in every run to 09-05.
        return block.get("quadrant")
    return block.get("value")


def fields_of(dim):
    """The enum field(s) inside a block that carry the coordinate we report."""
    return {"structural":   ("scale",),
            "cooperative":  ("status", "maxim_violated"),
            "social_field": ("quadrant",)}.get(dim, (dim,))


def field_agreement(votes_rec, dim):
    """Agreement on the reported field(s), not on the whole block.

    categorical_signature() builds a block's identity from ALL its enum fields, so the
    block-level `agreed` drops whenever ANY field wobbles: a 2/3 on `structural` hid a
    unanimous `scale` in the 2026-09-07 run. Conjunction verdicts (cooperative) take the
    weakest constituent field. Returns (agreed_string, distribution_subset).
    """
    dist = (votes_rec or {}).get("distribution") or {}
    n = (votes_rec or {}).get("n")
    tops = [max(dist[f].values()) for f in fields_of(dim)
            if isinstance(dist.get(f), dict) and dist[f]]
    if not tops or not n:
        return None, dist
    return f"{min(tops)}/{n}", {f: dist[f] for f in fields_of(dim) if f in dist}


def seed_baseline():
    """VOTED_2026_09_03 in the namespaced shape the runs file uses."""
    return {sid: {f"logos.{dim}": val for dim, val in dims.items()}
            for sid, dims in VOTED_2026_09_03.items()}


def load_baseline(runs_path):
    """Most recent recorded run, else the 09-03 seed. Returns (baseline, label)."""
    if runs_path.exists():
        try:
            data = json.loads(runs_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            sys.exit(f"cannot read baseline {runs_path}: {e}")
        runs = data.get("runs")
        if not runs and data.get("results"):
            runs = [data]                       # legacy single-run file
        if runs:
            last = runs[-1]
            when = (last.get("_meta") or {}).get("run", "unknown time")
            return _namespace(last.get("results", {})), f"previous run {when}"
    return seed_baseline(), "VOTED_2026_09_03 (seed)"


def _namespace(results):
    """Runs written before 2026-09-07 keyed logos dims bare ("structural").
    Rename those to the namespaced form so old runs stay comparable."""
    fixed = {}
    for sid, coords in (results or {}).items():
        fixed[sid] = {(f"logos.{k}" if k in LOGOS_DIMS else k): val
                      for k, val in (coords or {}).items()}
    return fixed


def same_text_groups(texts):
    """sids sharing byte-identical raw_text, as sorted groups of 2+.

    The strict control: identical input read independently in one run. The field
    store currently has NO such group — the two Ronald Cotton inferences are 88%
    similar, not identical (inf_0f31de7a carries an extra analytical paragraph),
    so they are two tellings, not a repeat. Kept because it is the honest test if
    a true duplicate ever enters.
    """
    groups = {}
    for sid, digest in texts.items():
        groups.setdefault(digest, []).append(sid)
    return [sorted(g) for g in groups.values() if len(g) > 1]


def same_case_groups(cases, texts):
    """sids sharing a case_id but NOT identical text — same case, different telling.

    Differences here measure sensitivity to how the case is told, which is a real
    property of the instrument but is NOT reproducibility. Reported separately so
    the two never get conflated.
    """
    groups = {}
    for sid, case in cases.items():
        if case:
            groups.setdefault(case, []).append(sid)
    return [sorted(g) for g in groups.values()
            if len(g) > 1 and len({texts[s] for s in g}) > 1]


def baseline_verdict(entry):
    """Runs-file entries are dicts; seed entries are bare strings."""
    if isinstance(entry, dict):
        return entry.get("verdict")
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="inferences/vote_stability_runs.json")
    ap.add_argument("--logos-only", action="store_true",
                    help="skip the conflict pass and tension (halves the call count, "
                         "but measures only the layer already known to be stable)")
    ap.add_argument("--keep-privacy-gate", action="store_true",
                    help="leave PRIVACY_GATE alone instead of disabling it for this run")
    args = ap.parse_args()

    # Deliberate for this test, and scoped to the run rather than to import: the field
    # cases are public record. Set at import it would silently disable the gate
    # process-wide for anything that merely imports this module.
    if not args.keep_privacy_gate:
        os.environ["PRIVACY_GATE"] = "off"
        print("PRIVACY_GATE = off (this run only; field cases are public record)")

    votes = _vote_count()
    inferences = sorted(FIELD.glob("inf_*.json"))
    per_inf = 1 if args.logos_only else 2
    print(f"VIVIFY_VOTES = {votes}   (majority-of-N per dimension)")
    print(f"scope: logos{'' if args.logos_only else ' + conflict + tension'}   "
          f"~{len(inferences) * per_inf * votes} calls "
          f"({len(inferences)} inferences x {per_inf} voted pass(es) x {votes})\n")

    runs_path = ROOT / args.out
    baseline, baseline_label = load_baseline(runs_path)
    print(f"diffing against: {baseline_label}\n")

    out = {"_meta": {"run": datetime.now(timezone.utc).isoformat(),
                     "votes": votes,
                     "agreed_semantics": "per-field (runs before 2026-09-07 are block-level)",
                     "scope": "logos" if args.logos_only else "logos+conflict+tension",
                     "compared_to": baseline_label},
           "results": {}}
    agree = differ = no_base = 0
    tension_drift = []
    texts, labels, cases = {}, {}, {}

    for p in inferences:
        inf = json.loads(p.read_text())
        sid = inf["id"]
        label = f"{inf.get('case_id')}{'*' if inf.get('canonical') else ''}"
        texts[sid] = hashlib.sha256(inf.get("raw_text", "").encode()).hexdigest()
        labels[sid] = label
        cases[sid] = inf.get("case_id")
        try:
            tagged = logos_fused.run(copy.deepcopy(inf))
            if not args.logos_only:
                tagged = conflict_operator.run(tagged)
                tagged = tension_score.score_inference(tagged)
        except LLMUnavailable as e:
            sys.exit(f"LLM unavailable: {e}")

        print(f"=== {label}  ({sid}) ===")
        out["results"][sid] = {}
        measured = [(f"logos.{d}", (tagged.get("logos") or {}).get(d, {}), d)
                    for d in LOGOS_DIMS]
        if not args.logos_only:
            conflict = tagged.get("conflict") or {}
            measured += [(f"conflict.{d}", conflict, d) for d in CONFLICT_DIMS]

        for key, block, dim in measured:
            now = (verdict(dim, block) if key.startswith("logos.")
                   else block.get(dim))
            votes_rec = block.get("_votes") or {}
            block_agreed = f"{votes_rec.get('agreed')}/{votes_rec.get('n')}"
            field_agreed, field_dist = field_agreement(votes_rec, dim)
            rec = {"verdict": now,
                   "agreed": field_agreed or block_agreed,
                   "block_agreed": block_agreed,
                   "distribution": field_dist or votes_rec.get("distribution")}
            numbers = {f: block.get(f) for f in NUMBERS.get(dim, ())}
            if dim == "terrain":
                numbers["draws"] = ((votes_rec.get("by_dim") or {})
                                    .get("terrain", {}).get("distances"))
            if numbers:
                rec["numbers"] = numbers
            out["results"][sid][key] = rec
            prev = baseline_verdict((baseline.get(sid) or {}).get(key))
            if prev is None:
                mark = "(no voted baseline)"; no_base += 1
            elif str(now) == str(prev):
                mark = f"agrees with {baseline_label.split()[0]}"; agree += 1
            else:
                mark = f"** DIFFERS ({prev}) **"; differ += 1
            note = "" if rec["agreed"] == block_agreed else f" [block {block_agreed}]"
            if dim == "social_field":
                note += " [quadrant derived; spread is the drawn label]"
            if numbers:
                note += f" {numbers}"
            print(f"  {key:20} {str(now):24} {rec['agreed']:5}  {mark}{note}")

        if not args.logos_only:
            tension = tagged.get("tension") or {}
            out["results"][sid]["tension"] = {k: tension.get(k) for k in TENSION_KEYS}
            prev_t = (baseline.get(sid) or {}).get("tension") or {}
            bits = []
            for k in TENSION_KEYS:
                now_v, prev_v = tension.get(k), prev_t.get(k)
                if isinstance(now_v, (int, float)) and isinstance(prev_v, (int, float)):
                    d = round(now_v - prev_v, 4)
                    bits.append(f"{k}={now_v} (Δ{d:+})")
                    if k == "predicted":
                        tension_drift.append(abs(d))
                else:
                    bits.append(f"{k}={now_v}")
            print(f"  {'tension':20} {'  '.join(bits)}")
        print()

    # The tightest available test: identical input read independently in ONE run.
    # Cross-session agreement compares different cases holding their values and
    # cannot see this.
    control = {"groups": [], "agree": 0, "differ": 0}
    strict = [(g, "same-text control (identical input)", "** DIFFERS on identical input **")
              for g in same_text_groups(texts)]
    loose = [(g, "same case, DIFFERENT telling — text sensitivity, not reproducibility",
              "** differs between tellings **")
             for g in same_case_groups(cases, texts)]
    if not strict:
        print("same-text control: no byte-identical pair in the store "
              "(the two Cotton tellings differ; see same_text_groups docstring)\n")
    for group, heading, marker in strict + loose:
        head = group[0]
        names = " vs ".join(f"{labels[s]} ({s})" for s in group)
        print(f"=== {heading}: {names} ===")
        g_agree = g_differ = 0
        for key in [k for k in out["results"][head] if k != "tension"]:
            vals = [out["results"][sid].get(key, {}).get("verdict") for sid in group]
            if len(set(map(str, vals))) == 1:
                g_agree += 1
            else:
                g_differ += 1
                print(f"  {key:20} " + "  vs  ".join(str(v) for v in vals) + f"   {marker}")
        preds = [(out["results"][sid].get("tension") or {}).get("predicted") for sid in group]
        if all(isinstance(v, (int, float)) for v in preds) and preds:
            print(f"  {'tension.predicted':20} " + "  vs  ".join(str(v) for v in preds)
                  + f"   spread {round(max(preds) - min(preds), 4)}")
        total = g_agree + g_differ
        print(f"  -> {g_agree} of {total} coordinates agree"
              + (f"  ({g_differ / total:.1%} disagreement)" if total else "") + "\n")
        control["groups"].append({"sids": group, "kind": heading,
                                  "agree": g_agree, "differ": g_differ})
        control["agree"] += g_agree
        control["differ"] += g_differ
    if control["groups"]:
        out["_meta"]["same_text_control"] = control

    compared = agree + differ
    out["_meta"]["voted_vs_voted"] = {"agree": agree, "differ": differ,
                                      "no_baseline": no_base, "compared": compared}
    print(f"categorical coordinates: {agree} agree, {differ} differ of {compared} "
          f"compared ({no_base} had no voted baseline and were recorded only)")
    if compared:
        print(f"  -> {differ / compared:.1%} disagreement this run")
    print("  single-draw baseline was 4 flipped / 6 split of 36 (11.1% / 16.7%) — "
          "different denominator, so compare rates not counts")
    if tension_drift:
        print(f"tension predicted drift: mean |Δ| {sum(tension_drift)/len(tension_drift):.4f}, "
              f"max |Δ| {max(tension_drift):.4f} (numeric — excluded from the counts above)")

    data = {"runs": []}
    if runs_path.exists():
        try:
            existing = json.loads(runs_path.read_text())
            data = existing if "runs" in existing else (
                {"runs": [existing]} if existing.get("results") else {"runs": []})
        except (json.JSONDecodeError, OSError):
            pass                                # unreadable prior file: start fresh
    data["runs"].append(out)
    runs_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {runs_path}  (run {len(data['runs'])}; prior runs kept)")


if __name__ == "__main__":
    main()

# llm: claude-opus-5 | 2026-09-05 | repos/vivify-operators/vote_stability_check.py | created — step 1 of stabilisation: voted-vs-voted cross-session comparison, the only honest control for whether repeat-and-vote reduces drift; store never written
# llm: claude-opus-5 | 2026-09-07 | repos/vivify-operators/vote_stability_check.py | `agreed` is now PER-FIELD (block-level signature hid a unanimous scale behind a language_mode wobble); block value kept as block_agreed
# llm: claude-opus-5 | 2026-09-07 | repos/vivify-operators/vote_stability_check.py | verdict() reads social_field.quadrant (it had silently recorded None every run); same-text control compares identical raw_text read independently within one run
# llm: claude-opus-5 | 2026-09-07 | repos/vivify-operators/vote_stability_check.py | measure conflict.terrain/window + tension (the layers the same-text Cotton pair shows actually drift), --logos-only for old scope; PRIVACY_GATE moved out of import into main(); baseline now read from the previous recorded run and runs APPEND instead of overwriting; report denominator explicitly

# llm: claude-opus-5 | 2026-09-11 | repos/vivify-operators/vote_stability_check.py | record the numbers behind the derived bins (terrain_distance + per-draw positions, social_field grid/group) so bin edges can be re-cut from the record
