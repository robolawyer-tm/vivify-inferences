"""
tension_score — FABRIC analysis: three-number tension over real signals

Scores each inference with predicted, confirmed, and calibration_delta tension,
replacing the dead lexical left/right keyword overlap (disjoint-by-nature
vocabularies pinned it at 1.0 storewide).

- predicted: the model's judgment of un-truth, from operator coordinates —
  resonance surface↔underlying gap (illusion) blended with conflict alarms.
  Available wherever operators ran, even mid-conflict with no correction in text.
- confirmed: ground-truth un-truth, from right_pass claimed-vs-actual
  discrepancies — log-ratio magnitude where numeric, 1.0 per categorical
  contradiction, squashed to 0-1. Available only where the baseline surfaced
  in the text (e.g. exoneration records) — the calibration corpus property.
- calibration_delta: predicted - confirmed where both exist. Negative = the
  operator under-smelled confirmed un-truth = operator error made numeric =
  the evolution gradient.
- Legacy scalar tension_score = predicted, falling back to confirmed, else
  None (honest "unmeasured", replacing the junk 1.0s).
- v1 weights are hand-set and documented inline (prototyping stance);
  emergence of weights from calibration corpus is the eventual replacement.

Design origin: 2026-07-13 rewire conversation — "does the judgment match the
count" — a question about the world, not the encoding.
"""

import re
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json
from inference import case_key, is_canonical


INFERENCES_DIR = Path("inferences")
INDEX_FILE = INFERENCES_DIR / "index.json"

# v1 hand-set weights ---------------------------------------------------------

# resonance value → base tension level (times operator confidence)
RESONANCE_BASE = {"harmony": 0.05, "friction": 0.5, "illusion": 1.0}

# blend: resonance carries the signal, conflict alarms corroborate
RESONANCE_WEIGHT = 0.8
CONFLICT_WEIGHT = 0.2

# confirmed squash: total_magnitude / (total_magnitude + K);
# half-saturation at K — "four solid contradictions read 0.5"
CONFIRMED_K = 4.0

BASELINE_SOURCES_FILE = Path(__file__).parent / "config" / "baseline_sources.json"


def validated_sources():
    """Sources whose corrections count as ground truth (config/baseline_sources.json).

    - Only these sources can produce confirmed tension / calibration_delta —
      the contamination guard keeping research material out of the gradient
    - Missing config = empty set = nothing confirms (fail-closed)
    """
    data = read_json(BASELINE_SOURCES_FILE)
    return set(data.get("validated", [])) if data else set()

WORD_NUMBERS = {
    "zero": 0, "one": 1, "single": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "hundred": 100, "thousand": 1000, "million": 1000000,
}


def _numbers_in(value):
    """Extract all numbers from a value: digits (commas stripped) + number words.

    - Returns list of floats; empty list = no quantities found
    """
    text = str(value).lower()
    nums = [float(n) for n in re.findall(r"\d+\.?\d*", text.replace(",", ""))]
    nums += [float(WORD_NUMBERS[w])
             for w in re.findall(r"[a-z]+", text) if w in WORD_NUMBERS]
    return nums


def discrepancy_magnitude(disc):
    """Magnitude of one claimed-vs-actual discrepancy.

    - Both sides numeric: 1.0 + |log10(scale ratio)| — scale = largest number
      on each side, so '1 in 694,000' vs '1 in 16' reads ~5.6
    - Either side non-numeric: 1.0 (categorical contradiction, counts once)
    """
    import math
    claimed = _numbers_in(disc.get("claimed", ""))
    actual = _numbers_in(disc.get("actual", ""))
    if claimed and actual:
        a, b = max(claimed), max(actual)
        if a > 0 and b > 0:
            return 1.0 + abs(math.log10(a / b))
    return 1.0


def confirmed_tension(inference):
    """Ground-truth tension from right_pass discrepancies, 0-1.

    - None if the source is not baseline-validated (config/baseline_sources.json)
      — a correction in research/manual/model-generated text is a citation, not
      ground truth, and must not enter the calibration_delta gradient
    - None if real right_pass never ran (no right_facts key) — unmeasured
    - 0.0 if it ran on a validated source and found no claimed-vs-actual pairs
    - Otherwise squashed sum of discrepancy magnitudes
    """
    if inference.get("source") not in validated_sources():
        return None
    if "right_facts" not in inference:
        return None
    total = sum(discrepancy_magnitude(d)
                for d in inference.get("discrepancies", []))
    return round(total / (total + CONFIRMED_K), 4)


def predicted_tension(inference):
    """The operators' judgment of un-truth, 0-1, from stored coordinates.

    - None if no resonance coordinate (operators never ran) — unmeasured
    - resonance component: RESONANCE_BASE[value] * confidence
    - conflict component: fraction of four alarm signals present, times
      conflict confidence — schema=entangled, behavior in
      {suppression, escalating}, window=rationalizing,
      escalation_phase in {threshold, exponential}
    - blend 0.8/0.2; resonance stands alone when no conflict block
    """
    resonance = inference.get("logos", {}).get("resonance")
    if not resonance or resonance.get("value") not in RESONANCE_BASE:
        return None

    res_component = (RESONANCE_BASE[resonance["value"]]
                     * resonance.get("confidence", 1.0))

    conflict = inference.get("conflict")
    if not conflict:
        return round(res_component, 4)

    alarms = [
        conflict.get("schema") == "entangled",
        conflict.get("behavior") in ("suppression", "escalating"),
        conflict.get("window") == "rationalizing",
        conflict.get("escalation_phase") in ("threshold", "exponential"),
    ]
    con_component = (sum(alarms) / len(alarms)) * conflict.get("confidence", 1.0)

    return round(RESONANCE_WEIGHT * res_component
                 + CONFLICT_WEIGHT * con_component, 4)


def score_inference(inference):
    """Attach the three-number tension block and legacy scalar to an inference.

    - tension.predicted / tension.confirmed / tension.calibration_delta
      (each None when its signal source is absent — unmeasured, not zero)
    - tension_score (legacy scalar) = predicted, else confirmed, else None
    - Returns updated inference
    """
    inference = dict(inference)
    predicted = predicted_tension(inference)
    confirmed = confirmed_tension(inference)
    delta = (round(predicted - confirmed, 4)
             if predicted is not None and confirmed is not None else None)

    inference["tension"] = {
        "predicted": predicted,
        "confirmed": confirmed,
        "calibration_delta": delta,
    }
    inference["tension_score"] = predicted if predicted is not None else confirmed
    return inference


def score_all(inferences_dir=None, dry_run=False):
    """Score all inferences and update their files.

    - Returns list of (id, path, tension dict, legacy scalar), measured first,
      sorted by legacy scalar high to low
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    results = []

    for path in inferences_dir.rglob("inf_*.json"):
        inference = read_json(path)
        if not inference:
            continue
        updated = score_inference(inference)
        if not dry_run:
            write_json(path, updated)
        results.append((
            updated["id"],
            str(path),
            updated["tension"],
            updated["tension_score"],
        ))

    return sorted(results, key=lambda x: (x[3] is None, -(x[3] or 0)))


def gradient(inferences_dir=None):
    """The calibration gradient — one point per case, variant tellings excluded.

    Every inference still carries its own three numbers; scoring is per-text and
    unchanged. This is the aggregate view, and it must count each underlying case
    once: a case entered twice would otherwise vote twice on how well the
    operators are calibrated, and the more re-tellings a case has, the louder its
    delta gets. That is measurement of the instrument leaking into the gradient.

    - A point needs a measured calibration_delta (predicted AND confirmed present,
      so in practice a baseline-validated source)
    - Canonical telling of a case = the one marked `canonical: true`, else the
      earliest timestamp. Earliest-wins alone is wrong whenever a later telling is
      the better source — which is the usual reason to re-tell a case at all — so
      the mark exists to override arrival order.
    - Returns (points, variants), each a list of dicts with id, case, delta
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    by_case = {}

    for path in inferences_dir.rglob("inf_*.json"):
        inference = read_json(path)
        if not inference:
            continue
        delta = (inference.get("tension") or {}).get("calibration_delta")
        if delta is None:
            continue
        entry = {
            "id": inference["id"],
            "case": case_key(inference),
            "delta": delta,
            "canonical": is_canonical(inference),
            "timestamp": inference.get("timestamp", ""),
            "path": str(path),
        }
        by_case.setdefault(entry["case"], []).append(entry)

    points, variants = [], []
    for tellings in by_case.values():
        tellings.sort(key=lambda e: e["timestamp"])
        marked = [t for t in tellings if t["canonical"]]
        chosen = marked[0] if marked else tellings[0]
        points.append(chosen)
        variants.extend(t for t in tellings if t is not chosen)

    return sorted(points, key=lambda e: -abs(e["delta"])), variants


def beneficial_signals(inferences_dir=None, threshold=0.5):
    """Find inferences where measured tension exceeds threshold — intervention candidates.

    - Uses the legacy scalar (predicted-first); unmeasured (None) never signals
    - Returns list of dicts with id, tension numbers, left_keywords, category_paths
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    signals = []

    for path in inferences_dir.rglob("inf_*.json"):
        inference = read_json(path)
        if not inference:
            continue
        score = inference.get("tension_score")
        if score is not None and score >= threshold:
            signals.append({
                "id": inference["id"],
                "tension_score": score,
                "tension": inference.get("tension", {}),
                "left_keywords": inference.get("left_keywords", []),
                "category_paths": inference.get("category_paths", []),
                "source": inference.get("source", "unknown")
            })

    return sorted(signals, key=lambda x: -x["tension_score"])


def prediction_output(inference):
    """Generate a Phase 5 bottled prediction API response for a single inference.

    - beneficial_score: measured tension (0.0 when unmeasured)
    - resolution_paths: category_paths from the inference
    - tension_signals: top left keywords by co-occurrence strength
    - Returns dict matching the Phase 5 API shape
    """
    score = inference.get("tension_score")
    return {
        "id": inference["id"],
        "beneficial_score": score if score is not None else 0.0,
        "tension": inference.get("tension", {}),
        "resolution_paths": inference.get("category_paths", []),
        "tension_signals": inference.get("left_keywords", [])[:4],
        "source": inference.get("source", "unknown")
    }


def _fmt(x):
    """Render a tension number for table output; None = unmeasured."""
    if x is None:
        return "  --  "
    return f"{x:+.4f}" if x < 0 else f"{x:.4f}"


def usage():
    print("Usage: tension_score.py              score all inferences")
    print("       tension_score.py --signals     show high-tension intervention candidates")
    print("       tension_score.py --predict     show Phase 5 API output for all inferences")
    print("       tension_score.py --dry-run     score without writing files")
    sys.exit(1)


def main():
    dry_run = "--dry-run" in sys.argv

    if "--signals" in sys.argv:
        signals = beneficial_signals()
        if not signals:
            print("No high-tension inferences found. Score first.")
            return
        print(f"High-tension intervention candidates (tension >= 0.5):\n")
        for s in signals:
            t = s.get("tension", {})
            print(f"  {s['id']}  predicted: {_fmt(t.get('predicted'))}  "
                  f"confirmed: {_fmt(t.get('confirmed'))}  "
                  f"delta: {_fmt(t.get('calibration_delta'))}")
            print(f"    source:   {s['source']}")
            print(f"    keywords: {', '.join(s['left_keywords'][:5])}")
            print(f"    paths:    {', '.join(s['category_paths'][:2])}")
            print()
        return

    if "--predict" in sys.argv:
        print("Phase 5 — Bottled Prediction API output:\n")
        for path in INFERENCES_DIR.rglob("inf_*.json"):
            inference = read_json(path)
            if inference:
                print(json.dumps(prediction_output(inference), indent=2))
                print()
        return

    results = score_all(dry_run=dry_run)

    if not results:
        print("No inferences found.")
        return

    measured = [(i, p, t, s) for i, p, t, s in results if s is not None]
    unmeasured = len(results) - len(measured)

    print(f"Scored {len(results)} inferences "
          f"({len(measured)} measured, {unmeasured} unmeasured):\n")
    if measured:
        print(f"  {'id':<14} {'predicted':>9} {'confirmed':>9} {'delta':>8}")
    for inf_id, path, t, scalar in measured:
        bar = "█" * int((scalar or 0) * 20)
        print(f"  {inf_id:<14} {_fmt(t['predicted']):>9} {_fmt(t['confirmed']):>9} "
              f"{_fmt(t['calibration_delta']):>8}  {bar}")
        print(f"    {path}")
    print()
    if measured:
        avg = sum(s for _, _, _, s in measured) / len(measured)
        print(f"Average measured tension: {avg:.4f}")
        print(f"Peak: {measured[0][3]:.4f}  ({measured[0][0]})")

    points, variants = gradient()
    if points:
        mean_delta = sum(abs(p["delta"]) for p in points) / len(points)
        print(f"Calibration gradient: {len(points)} point(s), "
              f"mean |delta| {mean_delta:.4f}")
        if variants:
            print(f"  {len(variants)} variant telling(s) excluded "
                  f"(same case as a canonical point):")
            for v in variants:
                print(f"    {v['id']}  case={v['case']}  delta={_fmt(v['delta'])}")
            unmarked = sorted({v["case"] for v in variants}
                              - {p["case"] for p in points if p["canonical"]})
            for case in unmarked:
                print(f"  !! {case}: no telling marked canonical — arrival order "
                      f"chose the point. Set \"canonical\": true on the one that "
                      f"should count.")
    if unmeasured:
        print(f"Unmeasured (no operator coordinates, no real right_pass): {unmeasured}")


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/tension_score.py | created — left/right divergence scoring, beneficial signals, Phase 5 prediction output
# llm: claude-fable-5 | 2026-07-13 | repos/vivify-operators/tension_score.py | three-number rewire: predicted (resonance gap + conflict alarms), confirmed (discrepancy log-magnitudes), calibration_delta (the gradient); legacy scalar = predicted??confirmed??None, junk lexical-overlap formula removed
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/tension_score.py | gradient() — one calibration point per case, earliest telling canonical, later ones reported as excluded variants; per-inference scoring unchanged
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/tension_score.py | gradient() prefers an explicit canonical telling over earliest-timestamp, and warns when arrival order silently decided a multi-telling case
