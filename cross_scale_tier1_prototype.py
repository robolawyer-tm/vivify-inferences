#!/usr/bin/env python3
"""
cross_scale_tier1_prototype.py — throwaway prototype, does NOT touch cross_scale.py

Re-ranks the current store's cross-scale links by folding the Tier-1 confirmation
factor into link strength, to see what "wire the Tier-1 coupling into cross_scale
weights" does in real numbers.

  base strength   = Σ rarity(shared dims)                     (what cross_scale.py does now)
  conf_factor     = geomean(confirmed_a, confirmed_b)         (0 if either is unmeasured/None)
  boosted (1+f)   = base × (1 + conf_factor)                  (primary design: reward, don't erase)
  gated (×f)      = base × conf_factor                        (aggressive variant: ground-truth-only)

confirmed comes from tension.confirmed, computed ONLY for baseline_sources
(innocence_project) — so the boost can only come from validated ground truth.
Run from the repo root: python3 cross_scale_tier1_prototype.py
"""

import math
from pathlib import Path
import cross_scale as cs


def confirmed_map(inferences_dir="inferences"):
    """id -> tension.confirmed (may be None) for every inference in the store."""
    out = {}
    for path in Path(inferences_dir).rglob("inf_*.json"):
        inf = cs.read_json(path)
        if not inf:
            continue
        out[inf.get("id", path.stem)] = inf.get("tension", {}).get("confirmed")
    return out


def conf_factor(ca, cb):
    """Geometric mean of two confirmed values; 0 if either is unmeasured (None)."""
    if ca is None or cb is None:
        return 0.0
    return math.sqrt(ca * cb)


def main():
    usable, skipped = cs.load_signed()
    conf = confirmed_map()
    links = cs.find_links(usable, threshold=2)

    rows = []
    for link in links:
        a, b = link["inferences"]
        ca, cb = conf.get(a["id"]), conf.get(b["id"])
        f = conf_factor(ca, cb)
        base = link["strength"]
        rows.append({
            "a": a["id"], "b": b["id"],
            "scales": "↔".join(link["scales"]),
            "shared": link["shared"],
            "ca": ca, "cb": cb, "f": f,
            "base": base,
            "boosted": round(base * (1 + f), 3),
            "gated": round(base * f, 3),
        })

    def show(title, key):
        ranked = sorted(rows, key=lambda r: -r[key])
        print(f"\n=== {title} — top 8 by {key} ===")
        print(f"{'rank':>4}  {'strength':>8}  {'base':>6}  {'shared':>6}  {'conf_a':>7} {'conf_b':>7} {'factor':>6}  pair")
        for i, r in enumerate(ranked[:8], 1):
            ca = f"{r['ca']:.3f}" if r['ca'] is not None else "  —  "
            cb = f"{r['cb']:.3f}" if r['cb'] is not None else "  —  "
            print(f"{i:>4}  {r[key]:>8.3f}  {r['base']:>6.3f}  {r['shared']:>6}  "
                  f"{ca:>7} {cb:>7} {r['f']:>6.3f}  {r['a']} {r['scales']} {r['b']}")

    print(f"Store: {len(usable)} usable, {len(skipped)} skipped, {len(links)} links")
    n_conf = sum(1 for r in rows if r["f"] > 0)
    print(f"Links with BOTH ends confirmed (factor > 0): {n_conf} of {len(rows)}")

    show("BASELINE (current cross_scale.py)", "base")
    show("BOOSTED  strength × (1 + conf_factor)", "boosted")
    show("GATED    strength × conf_factor (ground-truth-only)", "gated")

    # explicit before/after on the two field cases
    print("\n=== the field-case link, tracked across all three rankings ===")
    for r in rows:
        if r["f"] > 0:
            print(f"  {r['a']} {r['scales']} {r['b']}: "
                  f"base={r['base']}  boosted={r['boosted']}  gated={r['gated']}  "
                  f"(conf {r['ca']}×{r['cb']} → factor {r['f']:.3f})")


if __name__ == "__main__":
    main()
