#!/usr/bin/env python3
"""
cross_scale.py — store-level operator: cross-scale signature isomorphism

Connects inferences that the per-item logos operators leave isolated. Every logos
operator tags one inference at a time; nothing compares one inference's coordinate
signature to another's. This pass reads the whole inference store and surfaces pairs
whose dynamic signature is isomorphic but whose social scale differs — e.g. a secrecy
pattern in one person's testimony matching an institutional suppression pattern.

The signature is the existing Psi-Phi-Omega fingerprint, read from fields already
produced by the logos and conflict operators (no new schema dimensions):
  Psi  (coherence)      = resonance.value + cooperative.status
  Omega (ignition cost) = tension_score, banded
  dynamic               = conflict.schema + conflict.behavior + conflict.terrain
The scale axis is logos.structural.scale (falls back to logos.structural.layer).
Phi (integration) is the link structure this operator builds — not a per-item field.

Schema: pillars/logos/logos_combined_v01.json#structural
"""

import sys
import json
import math
import argparse
from pathlib import Path
from collections import Counter
from itertools import combinations

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json
from inference import case_key

INFERENCES_DIR = Path("inferences")
LINKS_FILE = INFERENCES_DIR / "cross_scale.json"
MANIFEST_FILE = INFERENCES_DIR / "_tagging_manifest.json"

# Signature dimensions read from each inference. Scale is excluded on purpose —
# it is the axis the comparator looks for difference along, not similarity.
SIGNATURE_DIMS = [
    "conflict_schema",
    "conflict_behavior",
    "conflict_terrain",
    "resonance",
    "cooperative_status",
    "tension_band",
]


def tension_band(score):
    """Bucket the continuous tension_score (Omega) into a coarse band.

    - Exact float equality never matches across inferences; bands do.
    - Returns 'high' | 'mid' | 'low' | None
    """
    if score is None:
        return None
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "mid"
    return "low"


def signature(inf):
    """Extract the (scale, dims) fingerprint from one inference.

    - dims holds only the SIGNATURE_DIMS that are actually present (None dropped)
    - scale comes from logos.structural.scale, falling back to .layer
    - Returns (scale, {dim: value}) — scale is None if the inference is untagged
    """
    logos = inf.get("logos", {})
    structural = logos.get("structural", {})
    conflict = inf.get("conflict", {})

    scale = structural.get("scale") or structural.get("layer")

    raw = {
        "conflict_schema":    conflict.get("schema"),
        "conflict_behavior":  conflict.get("behavior"),
        "conflict_terrain":   conflict.get("terrain"),
        "resonance":          logos.get("resonance", {}).get("value"),
        "cooperative_status": logos.get("cooperative", {}).get("status"),
        "tension_band":       tension_band(inf.get("tension_score")),
    }
    dims = {k: v for k, v in raw.items() if v is not None}
    return scale, dims


def load_signed(inferences_dir=None):
    """Load every inference that carries a scale and at least two signature dims.

    - Returns (usable, skipped) where usable is a list of dicts and skipped is a
      list of (id, reason) for inferences that cannot participate
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    usable, skipped = [], []

    for path in inferences_dir.rglob("inf_*.json"):
        inf = read_json(path)
        if not inf:
            continue
        scale, dims = signature(inf)
        inf_id = inf.get("id", path.stem)
        if scale is None:
            skipped.append((inf_id, "no scale (run structural_operator)"))
            continue
        if len(dims) < 2:
            skipped.append((inf_id, f"only {len(dims)} signature dim(s)"))
            continue
        usable.append({"id": inf_id, "case": case_key(inf), "path": str(path),
                       "scale": scale, "dims": dims})

    return usable, skipped


def info_weights(usable):
    """Compute an information weight for every (dim, value) seen in the store.

    - weight = -log(df / N): a value shared by all cases carries no signal (0);
      a rare value carries more. This stops near-constant dims (resonance=harmony,
      tension_band=high) from inflating link strength.
    - df and N are counted over CASES, not inferences: a case told twice must not
      make its own coordinate values look twice as common (which would silently
      discount every real link that shares them). A case whose two tellings
      disagree on a dim contributes both values, once each.
    - Returns dict {(dim, value): weight}
    """
    seen = set()
    for inf in usable:
        for pair in inf["dims"].items():
            seen.add((inf["case"], pair))
    n = len({inf["case"] for inf in usable})
    counts = Counter(pair for _, pair in seen)
    return {key: -math.log(df / n) for key, df in counts.items()}


def isomorphism(a, b):
    """Score how isomorphic two inference signatures are.

    - Shared = signature dims where both agree on the same value
    - A cross-scale link requires the two scales to differ
    - Two tellings of the SAME case never link: they are one observation entered
      twice, so any agreement between them measures the instrument, not the world.
      The same-scale rule already drops most of them, but a variant pair that
      disagrees on scale is exactly the interesting disagreement — and would
      otherwise top the ranking as a spurious cross-scale isomorphism.
    - Returns (shared_count, shared_dims) or (0, {}) if same scale or same case
    """
    if a["scale"] == b["scale"] or a["case"] == b["case"]:
        return 0, {}
    shared = {
        k: a["dims"][k]
        for k in a["dims"].keys() & b["dims"].keys()
        if a["dims"][k] == b["dims"][k]
    }
    return len(shared), shared


def find_links(usable, threshold=2):
    """Find all cross-scale isomorphic pairs at or above the agreement threshold.

    - threshold = minimum number of shared signature dims to count as isomorphic
    - strength = summed information weight of the shared dims (discriminating signal)
    - Returns list of link dicts sorted by strength, then raw shared count, descending
    """
    weights = info_weights(usable)
    links = []
    for a, b in combinations(usable, 2):
        shared_count, shared_dims = isomorphism(a, b)
        if shared_count >= threshold:
            strength = round(sum(weights[(k, v)] for k, v in shared_dims.items()), 3)
            links.append({
                "strength": strength,
                "shared": shared_count,
                "scales": sorted([a["scale"], b["scale"]]),
                "signature": {
                    k: {"value": v, "weight": round(weights[(k, v)], 3)}
                    for k, v in shared_dims.items()
                },
                "inferences": [
                    {"id": a["id"], "scale": a["scale"]},
                    {"id": b["id"], "scale": b["scale"]},
                ],
            })
    return sorted(links, key=lambda x: (-x["strength"], -x["shared"]))


def usage():
    print("Usage: cross_scale.py                 find cross-scale links, write cross_scale.json")
    print("       cross_scale.py --threshold N    min shared signature dims (default 2)")
    print("       cross_scale.py --dry-run        report without writing")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Cross-scale signature isomorphism over the inference store")
    parser.add_argument("--threshold", type=int, default=2, help="min shared signature dims (default 2)")
    parser.add_argument("--dry-run", action="store_true", help="report without writing cross_scale.json")
    args = parser.parse_args()

    usable, skipped = load_signed()

    # Completeness check: if tag_store.py left a manifest showing the store is only
    # partially tagged, the link map below is built on a partial signature set and
    # WILL under-count. Warn loudly rather than present a partial result as final.
    manifest = read_json(MANIFEST_FILE)
    if manifest and manifest.get("incomplete"):
        print(f"!! WARNING: store is partially tagged — {manifest['incomplete']} of "
              f"{manifest.get('total', '?')} inferences are incomplete "
              f"(manifest {manifest.get('at', '')}).")
        print("!! Cross-scale links below are computed on a PARTIAL store and will "
              "under-count. Run tag_store.py to finish, then re-run.\n")

    cases = len({inf["case"] for inf in usable})
    print(f"Inference store: {len(usable)} usable, {len(skipped)} skipped")
    if cases < len(usable):
        print(f"  {len(usable) - cases} variant telling(s) — {cases} distinct cases; "
              f"same-case pairs excluded from linking")
    print()

    if skipped:
        print("Skipped (cannot participate yet):")
        for inf_id, reason in skipped[:12]:
            print(f"  {inf_id}  — {reason}")
        if len(skipped) > 12:
            print(f"  ... and {len(skipped) - 12} more")
        print()

    if len(usable) < 2:
        print("Need at least 2 tagged inferences to compare. Run structural_operator")
        print("and conflict_operator across the store first, then re-run.")
        return

    links = find_links(usable, threshold=args.threshold)

    if not links:
        print(f"No cross-scale links at threshold {args.threshold}.")
        print("Either no isomorphic signatures span different scales, or lower --threshold.")
        return

    print(f"Cross-scale links (shared >= {args.threshold}, ranked by information strength):\n")
    for link in links:
        a, b = link["inferences"]
        sig = ", ".join(
            f"{k}={d['value']}" + (" (low-info)" if d["weight"] == 0 else "")
            for k, d in link["signature"].items()
        )
        print(f"  {a['id']} ({a['scale']})  <->  {b['id']} ({b['scale']})"
              f"   strength={link['strength']} shared={link['shared']}")
        print(f"    signature: {sig}")
        print()

    if not args.dry_run:
        write_json(LINKS_FILE, {
            "_operator": "cross_scale.py",
            "threshold": args.threshold,
            "usable": len(usable),
            "skipped": len(skipped),
            "links": links,
        })
        print(f"Wrote {len(links)} links to {LINKS_FILE}")


if __name__ == "__main__":
    main()

# llm: claude-opus-4-8 | 2026-06-15 | repos/vivify-operators/cross_scale.py | created — store-level cross-scale signature isomorphism operator (connective layer over logos/conflict coordinates)
# llm: claude-opus-4-8 | 2026-06-15 | repos/vivify-operators/cross_scale.py | added IDF-style info weighting — rank links by discriminating signal, flag near-constant dims as low-info
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/cross_scale.py | warn when _tagging_manifest.json shows a partial store — partial signature set under-counts links; surface it instead of presenting partial as final
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/cross_scale.py | same-case pairs excluded from linking (variant on a different scale would have topped the ranking spuriously); info_weights df/N counted over cases not inferences
